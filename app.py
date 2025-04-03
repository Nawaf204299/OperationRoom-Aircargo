
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
import numpy as np
import os
from werkzeug.utils import secure_filename
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'your_secret_key'

ADMIN_USERNAME = 'operationroom'
ADMIN_PASSWORD = 'Aircargo123'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

suspicious_keywords = [
    'powder', 'capsule', 'tablet', 'herb', 'herbal', 'extract', 'leaf', 'tea',
    'khat', 'supplement', 'medicine', 'sample', 'personal use', 'personal goods',
    'organic matter', 'resin', 'seeds', 'incense', 'oil', 'natural', 'botanical',
    'kava powder', 'kratom', 'herbal capsules', 'slimming tea', 'pain relief',
    'muscle relaxant', 'sleep aid', 'natural remedy', 'detox tea', 'cannabis',
    'cbd', 'thc', 'ayahuasca', 'magic mushrooms', 'indus clean', 'clean tea',
    'bio cleanse', 'body flush', 'slim pro', 'energy capsule', 'health supplement',
    'unknown origin', 'medical sample'
]

risky_countries = [
    'thailand', 'china', 'hong kong', 'netherlands', 'holland', 'united kingdom',
    'australia', 'nigeria', 'colombia', 'peru', 'mexico', 'pakistan', 'iran', 'india'
]

risky_areas = [
    'international city', 'ajman', 'sharjah', 'muhaisnah', 'al qusais', 'deira',
    'hor al anz', 'naif', 'rolla', 'industrial area'
]

def analyze_manifest(filepath):
    xls = pd.ExcelFile(filepath)
    df = xls.parse(xls.sheet_names[0])
    df.columns = [str(col).strip() for col in df.columns]
    df['Suspicion_Score'] = 0

    if 'Description' in df.columns:
        df['Description_clean'] = df['Description'].astype(str).str.lower()
        df['Suspicion_Score'] += df['Description_clean'].apply(
            lambda x: sum(kw in x for kw in suspicious_keywords)
        )

    if 'Origin Country' in df.columns:
        df['Origin_clean'] = df['Origin Country'].astype(str).str.lower()
        df['Country_Risk'] = df['Origin_clean'].apply(lambda x: any(c in x for c in risky_countries))
        df['Suspicion_Score'] += df['Country_Risk'].astype(int)

    if 'Importer Address 1' in df.columns or 'Importer Address 2' in df.columns:
        df['Address1_clean'] = df.get('Importer Address 1', "").astype(str).str.lower()
        df['Address2_clean'] = df.get('Importer Address 2', "").astype(str).str.lower()
        df['Address_Risk'] = df.apply(
            lambda row: any(area in row['Address1_clean'] or area in row['Address2_clean'] for area in risky_areas),
            axis=1
        )
        df['Suspicion_Score'] += df['Address_Risk'].astype(int)

    if 'Weight' in df.columns:
        df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce').fillna(0)
    else:
        df['Weight'] = 0

    if 'USD_Value' in df.columns:
        df['USD_Value'] = pd.to_numeric(df['USD_Value'], errors='coerce').fillna(0)
    else:
        df['USD_Value'] = 0

    df['Value_to_Weight'] = df.apply(lambda row: row['USD_Value'] / row['Weight'] if row['Weight'] > 0 else np.nan, axis=1)
    df['Low_Value_Heavy'] = df['Value_to_Weight'] < 10
    df['Abnormal_Weight'] = df['Weight'] > 100

    df['Suspicion_Score'] += df['Low_Value_Heavy'].astype(int)
    df['Suspicion_Score'] += df['Abnormal_Weight'].astype(int)

    top_suspects = df.sort_values(by=['Suspicion_Score', 'Weight'], ascending=[False, False]).head(10)
    top_suspects.to_excel('suspicion_results.xlsx', index=False)
    return top_suspects

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('index'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return "No file part in the request.", 400
    file = request.files['file']
    if file.filename == '':
        return "No file selected.", 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    try:
        results = analyze_manifest(filepath)
    except Exception as e:
        return f"<h2>Error during analysis:</h2><pre>{str(e)}</pre>", 500
    return render_template('results.html', tables=[results.to_html(classes='data')], titles=results.columns.values)

@app.route('/export/excel')
def export_excel():
    return send_file('suspicion_results.xlsx', as_attachment=True)

@app.route('/export/pdf')
def export_pdf():
    df = pd.read_excel('suspicion_results.xlsx').head(10)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    for header in df.columns[:4]:
        pdf.cell(40, 10, str(header), border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for item in row[:4]:
            pdf.cell(40, 10, str(item)[:20], border=1)
        pdf.ln()
    pdf.output("suspicion_results.pdf")
    return send_file("suspicion_results.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
