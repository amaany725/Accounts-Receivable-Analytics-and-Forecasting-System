import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import joblib
import requests
from database import engine

# load model
model = joblib.load('model/random_forest_model.pkl')
# =========================================
# LOAD HISTORICAL DATA
# =========================================

def load_historical_data(company):
    query = """
        SELECT *
        FROM historical_invoice
        WHERE company_name = %(company)s
    """

    df_hist = pd.read_sql(
        query,
        engine,
        params={
            'company': company
        }
    )

    return df_hist

def get_customer_features(customer_name, df_hist):
    history = df_hist[df_hist['Customer'] == customer_name]
    if len(history) == 0:
        # customer baru
        return {
            'customer_repeat_count': 0,
            'avg_delay_customer': 0,
            'late_ratio': 0,
            'last_delay': 0,
            'avg_amount_customer': 0,
            'delay_std': 0
        }
    
    delay = history['Delay'].dropna()

    return {
        'customer_repeat_count': len(history),
        'avg_delay_customer': delay.mean() if len(delay) > 0 else 0,
        'late_ratio': (delay > 0).mean() if len(delay) > 0 else 0,
        'last_delay': delay.iloc[-1] if len(delay) > 0 else 0,
        'avg_amount_customer': history['Total Amount'].mean(),
        'delay_std': delay.std() if len(delay) > 1 else 0
    }

def prepare_input(customer_name, order_type, customer_type, amount, term, df_hist):
    hist_feat = get_customer_features(customer_name, df_hist)
  
    customer_type_map = {
        'PT': [0,1,0],
        'UD': [0,0,1],
        'PERORANGAN': [1,0,0],
        'CV' : [0,0,0]
    }

    order_map = {
        'TRADING': [1,0],
        'WORKSHOP': [0,1],
        'PROJECT': [0,0]
    }

    input_data = {
        'customer_type_PERORANGAN': customer_type_map[customer_type][0],
        'customer_type_PT': customer_type_map[customer_type][1],
        'customer_type_UD': customer_type_map[customer_type][2],
        'Kategori Order_TRADING': order_map[order_type][0],
        'Kategori Order_WORKSHOP': order_map[order_type][1],
        'Term': term,
        'amount_log': np.log1p(amount),
        **hist_feat
    }

    return pd.DataFrame([input_data])

# =========================================
# ANALISIS TERM
# =========================================
def analyze_terms(customer_name, order_type, customer_type, amount, df_hist, model):
    results = []
    for term in range(0, 61, 5):
        input_df = prepare_input(
            customer_name,
            order_type,
            customer_type,
            amount,
            term,
            df_hist
        )
        prob = model.predict_proba(input_df)[0][1]
        results.append({
            'term': term,
            'prob_telat': prob
        })
    return pd.DataFrame(results)

# =========================================
# PURE BUSINESS RULE RECOMMENDATION
# =========================================
def recommend_term_business(prob):
    # VERY SAFE
    if prob < 0.30:
        return {
            'recommended_term': 60,
            'recommended_risk': prob,
            'risk_category': 'low',
            'description_status': 'safe'
        }


    # MEDIUM RISK
    elif prob < 0.69:
        return {
            'recommended_term': 30,
            'recommended_risk': prob,
            'risk_category': 'medium',
            'description_status': 'limited'
        }

    # HIGH RISK
    elif prob < 0.95:
        return {
            'recommended_term': 14,
            'recommended_risk': prob,
            'risk_category': 'high',
            'description_status': 'risky'
        }

    # VERY HIGH RISK
    else:
        return {
            'recommended_term': 0,
            'recommended_risk': prob,
            'risk_category': 'very_high',
            'description_status': 'danger'
        }

# =========================================
# PREDIKSI STATUS
# =========================================
def predict_payment_risk(input_df, model):
    pred = model.predict(input_df)[0]
    prob = model.predict_proba(input_df)[0][1]
    if pred == 1:
        status = "⚠️ Berisiko Telat"
    else:
        status = "✅ Cenderung Aman"

    return status, prob

# =========================================
# CATATAN KHUSUS CUSTOMER BERMASALAH
# =========================================
SPECIAL_NOTES = {

    # =====================
    # PROJECT
    # =====================

    "PT. Sigma Utama":
    """
Pernah mengalami pembayaran macet meski sudah diberi tempo dan DP.
Kasus sempat ditangani legal perusahaan karena masih menyisakan outstanding balance.
""",

    "Markas Besar Angkatan Laut Dinas Material":
    """
Keterlambatan dipengaruhi proses administrasi dan dokumen pajak yang lama,
namun pembayaran akhirnya tetap diselesaikan.
""",

    "PT. Wijaya Karya Industri dan Konstruksi":
    """
Memiliki riwayat keterlambatan berulang pada beberapa project,
terutama akibat pembayaran bertahap dan adanya project yang sempat macet.
""",


    # =====================
    # TRADING
    # =====================

    "Pelayaran Ryan Samudera Adijaya, PT":
    """
Pernah mengalami gagal penagihan hingga kasus masuk jalur hukum
dan akhirnya piutang dihapus karena kondisi perusahaan tidak dapat ditindaklanjuti.
""",

    "Toko Sumber Lancar":
    """
Memiliki tingkat keterlambatan sangat tinggi
dan operasional toko sudah berhenti/tutup.
""",

    "Industri Kapal Indonesia, PT":
    """
Riwayat keterlambatan cukup sering,
namun sebagian pembayaran besar masih berhasil ditagihkan
melalui penanganan khusus.
""",


    # =====================
    # WORKSHOP
    # =====================

    "Hamatek Indo, PT":
    """
Awalnya sistem cash,
namun diberi kelonggaran tempo karena volume transaksi besar
dengan pengawasan pelepasan material.
""",

    "Inti Karya Persada Teknik, PT":
    """
Awalnya menggunakan pembayaran cash,
lalu mulai diberi tempo pada transaksi tertentu
karena adanya hubungan dan kepercayaan bisnis.
""",

    "Buana Megah Teknik, PT":
    """
Memiliki riwayat keterlambatan tinggi akibat skema pelepasan material bertahap
sebelum seluruh pembayaran dilunasi.
""",
############## YG HAPUS PIUTANG #######################
    "Toko Sumber Lancar":
    """
    Retail DJ yang sudah tutup operasional.
    Sebagian piutang ditutup menggunakan barang, sisanya masih menjadi outstanding murni.
    """,

    "Dok Dan Perkapalan Surabaya, PT":
    """
    BUMN dengan kendala administrasi pajak.
    Invoice menggunakan PPN namun pembukuan pajak dari customer tidak diberikan sehingga outstanding menggantung.
    """,

    "SWTS Indonesia, PT":
    """
    Terdapat banyak nominal kecil akibat migrasi data dan invoice lama yang sebenarnya sudah dibayar namun belum tertutup sistem.
    """,

    "Citramas Heavy Industries, PT":
    """
    Customer workshop dengan histori penagihan sulit dan penolakan pembayaran pada beberapa invoice.
    """,

    "Adhi Persada Gedung, PT":
    """
    Kasus dialihkan ke pihak marketing karena customer mengalami kendala pembayaran akibat perpindahan tender project. Salesnya pak Adam
    """,

    "Karya Pembangunan Risky":
    """
    Merupakan cust sumber lancar. yang bersangkutan telah melakukan pembayaran ke marketing sumber lancar, namun marketing tidak menyerahkannya kepada Dimas Jaya.
    """,

    "Museum Angkut - Batu":
    """
    Terdapat invoice yang pernah masuk ke kas penghapusan piutang internal perusahaan.
    """,

    "Mohdar BSA, Bp":
    """
    Terdapat histori invoice yang pernah masuk ke pencatatan penghapusan piutang.
    """,

    "SMKN 1 Driyorejo":
    """
    Kasus pembayaran pernah diproses hukum dan pihak terkait sudah tidak dapat ditindaklanjuti.
    """
}
# =========================================
# AMBIL CATATAN KHUSUS CUSTOMER
# =========================================
def get_special_note(customer_name):

    for company in SPECIAL_NOTES:

        if company.lower() in customer_name.lower():

            return SPECIAL_NOTES[company]

    return None

# =========================================
# DESKRIPSI REKOMENDASI
# =========================================
def generate_business_description(
    customer_name,
    df_hist,
    recommendation
):

    history = df_hist[
        df_hist['Customer'] == customer_name
    ]

    is_new_customer = len(history) == 0
    term = recommendation['recommended_term']
    risk = recommendation['recommended_risk']
    special_note = get_special_note(customer_name)

    # =====================================
    # CUSTOMER BARU
    # =====================================
    if is_new_customer:
        return f"""
🔵 Customer belum memiliki histori transaksi sebelumnya.

Penilaian risiko dilakukan berdasarkan pola customer dengan karakteristik serupa.

Untuk transaksi awal, sistem menyarankan penggunaan term konservatif.

💡 Rekomendasi term:
{term} hari

📉 Probabilitas keterlambatan:
{risk:.2f}
"""

    # =====================================
    # LOW RISK
    # =====================================

    if recommendation['risk_category'] == 'low':

        return f"""
🟢 Customer memiliki histori pembayaran yang relatif baik.

Risiko keterlambatan tergolong rendah sehingga customer masih aman diberikan fleksibilitas pembayaran yang lebih panjang.

💡 Rekomendasi term:
{term} hari

📉 Probabilitas keterlambatan:
{risk:.2f}
"""

    # =====================================
    # MEDIUM
    # =====================================

    elif recommendation['risk_category'] == 'medium':

        return f"""
🟡 Customer menunjukkan potensi keterlambatan pada beberapa transaksi tertentu.

Namun berdasarkan simulasi berbagai skenario term pembayaran,
customer masih dapat diberikan term menengah dengan risiko
yang masih dapat ditoleransi.

💡 Rekomendasi term:
{term} hari

📉 Probabilitas keterlambatan:
{risk:.2f}
"""

    # =====================================
    # HIGH
    # =====================================

    elif recommendation['risk_category'] == 'high':

        return f"""
🟠 Customer memiliki kecenderungan keterlambatan pembayaran yang cukup tinggi.

Sistem tidak menemukan term dengan risiko yang benar-benar aman,
sehingga disarankan menggunakan term pendek
untuk meminimalkan risiko bisnis.

💡 Rekomendasi term:
{term} hari

📉 Probabilitas keterlambatan:
{risk:.2f}
"""

    # =====================================
    # VERY HIGH
    # =====================================

    else:

        return f"""
🔴 Customer teridentifikasi memiliki tingkat risiko keterlambatan
yang sangat tinggi pada hampir seluruh simulasi term pembayaran.

Walaupun beberapa term panjang dapat sedikit menurunkan probabilitas keterlambatan,
risiko bisnis masih tergolong tinggi.

💡 Disarankan:
- COD / pembayaran langsung
- atau evaluasi tambahan sebelum pemberian tempo

📉 Probabilitas keterlambatan terbaik:
{risk:.2f}
"""


def get_database_list(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(
        'https://account.accurate.id/api/db-list.do',
        headers=headers
    )
    data = response.json()
    return data
# =========================================
# PLOT TERM VS RISIKO
# =========================================
def plot_term_risk(df_terms, rekom_term=None):
    plt.figure(figsize=(8,5))
    plt.plot(
        df_terms['term'],
        df_terms['prob_telat'],
        marker='o'
    )

    # highlight rekomendasi
    if rekom_term is not None:
        rekom_row = df_terms[
            df_terms['term'] == rekom_term
        ]
        if not rekom_row.empty:
            x = rekom_row['term'].values[0]
            y = rekom_row['prob_telat'].values[0]
            plt.scatter(
                x,
                y,
                color='red',
                s=150,
                zorder=5,
                label=f'Rekomendasi ({x} hari)'
            )

            plt.annotate(
                f'{x} hari',
                (x, y),
                textcoords="offset points",
                xytext=(0,10),
                ha='center'
            )

    plt.xlabel('Term (hari)')
    plt.ylabel('Probabilitas Keterlambatan')
    plt.title('Term vs Risiko Keterlambatan')
    plt.grid()
    plt.legend()
    plt.savefig('static/plot.png')
    plt.close()
#================================================================================================

def generate_customer_behavior(df):
    notes = []

    # =====================================
    # AVG DELAY
    # =====================================
    avg_delay = df['Delay'].mean()
    if avg_delay > 14:
        notes.append(
            'Customer memiliki rata-rata keterlambatan tinggi.'
        )

    # =====================================
    # OUTSTANDING
    # =====================================
    unpaid = df[
        df['Status'] != 'Lunas'
    ]

    if len(unpaid) > 0:
        notes.append(
            'Masih terdapat invoice outstanding aktif.'
        )

    # =====================================
    # LATE RATIO
    # =====================================
    late_ratio = (
        (df['Delay'] > 0).mean()
    )

    if late_ratio > 0.6:
        notes.append(
            'Mayoritas invoice dibayar melewati jatuh tempo.'
        )

    # =====================================
    # CUSTOMER BARU
    # =====================================
    if len(df) <= 3:
        notes.append(
            'Customer masih tergolong baru dengan histori terbatas.'
        )
    return notes