from flask import Flask, render_template, Response, request
import psycopg2
import io
from PIL import Image
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for rendering
import matplotlib.pyplot as plt
import base64
from io import BytesIO

# Initialize the Flask application
app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Jakarta83'
}

def connect_to_db():
    """Establishes a connection to the database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def generate_charts():
    """Generates pie chart and bar charts for nama_petugas and kabupaten_kota distribution."""
    conn = connect_to_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT nama_petugas, row_1 AS provinsi, row_2 AS kabupaten_kota FROM ktp_data")
            data = cursor.fetchall()

            # Data processing for charts
            nama_petugas_count = {}
            provinsi_count = {}
            kabupaten_kota_count = {}

            for row in data:
                nama_petugas = row[0]
                provinsi = row[1]
                kabupaten_kota = row[2]
                nama_petugas_count[nama_petugas] = nama_petugas_count.get(nama_petugas, 0) + 1
                provinsi_count[provinsi] = provinsi_count.get(provinsi, 0) + 1
                kabupaten_kota_count[kabupaten_kota] = kabupaten_kota_count.get(kabupaten_kota, 0) + 1

            # Generate pie chart for nama_petugas
            fig1, ax1 = plt.subplots()
            ax1.pie(nama_petugas_count.values(), labels=nama_petugas_count.keys(), autopct='%1.1f%%')
            ax1.set_title('Distribution of Nama Petugas')
            pie_img = BytesIO()
            plt.savefig(pie_img, format='png')
            pie_img.seek(0)
            pie_chart_url = base64.b64encode(pie_img.getvalue()).decode()
            plt.close(fig1)

            # Generate bar chart for provinsi
            fig2, ax2 = plt.subplots(figsize=(12, 6))  # Wider chart
            ax2.bar(provinsi_count.keys(), provinsi_count.values())
            ax2.set_title('Distribution by Provinsi')
            ax2.set_xlabel('Provinsi')
            ax2.set_ylabel('Count')
            bar_provinsi_img = BytesIO()
            plt.savefig(bar_provinsi_img, format='png')
            bar_provinsi_img.seek(0)
            bar_provinsi_chart_url = base64.b64encode(bar_provinsi_img.getvalue()).decode()
            plt.close(fig2)

            # Generate bar chart for kabupaten_kota
            fig3, ax3 = plt.subplots(figsize=(12, 6))  # Wider chart
            ax3.bar(kabupaten_kota_count.keys(), kabupaten_kota_count.values())
            ax3.set_title('Distribution by Kabupaten/Kota')
            ax3.set_xlabel('Kabupaten/Kota')
            ax3.set_ylabel('Count')
            bar_kabupaten_img = BytesIO()
            plt.savefig(bar_kabupaten_img, format='png')
            bar_kabupaten_img.seek(0)
            bar_kabupaten_chart_url = base64.b64encode(bar_kabupaten_img.getvalue()).decode()
            plt.close(fig3)

            return pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url
        except Exception as e:
            print(f"Error generating charts: {e}")
            return None, None, None
        finally:
            conn.close()
    else:
        return None, None, None

def fetch_images_and_data(nama_petugas):
    """Fetches images and data from ktp_data and npwp_data based on nama_petugas."""
    conn = connect_to_db()
    if conn:
        try:
            cursor = conn.cursor()

            # Query for ktp_data image and table data
            cursor.execute("SELECT scanned_image, nama_petugas, row_4 AS NIK, row_6 AS Nama FROM ktp_data WHERE nama_petugas ILIKE %s", (f"%{nama_petugas}%",))
            ktp_result = cursor.fetchone()

            # Query for npwp_data image and table data
            cursor.execute("SELECT scanned_image, nama_petugas, row_1 AS Kantor_Dirjen, row_2 AS Nama_Wajib_Pajak, row_4 AS Nomor_Wajib_Pajak FROM npwp_data WHERE nama_petugas ILIKE %s", (f"%{nama_petugas}%",))
            npwp_result = cursor.fetchone()

            ktp_image_url = None
            npwp_image_url = None

            if ktp_result and ktp_result[0]:
                ktp_image = Image.open(io.BytesIO(ktp_result[0]))
                ktp_img_byte_arr = io.BytesIO()
                ktp_image.save(ktp_img_byte_arr, format='JPEG')
                ktp_img_byte_arr = ktp_img_byte_arr.getvalue()
                ktp_image_url = base64.b64encode(ktp_img_byte_arr).decode()

            if npwp_result and npwp_result[0]:
                npwp_image = Image.open(io.BytesIO(npwp_result[0]))
                npwp_img_byte_arr = io.BytesIO()
                npwp_image.save(npwp_img_byte_arr, format='JPEG')
                npwp_img_byte_arr = npwp_img_byte_arr.getvalue()
                npwp_image_url = base64.b64encode(npwp_img_byte_arr).decode()

            return {
                "ktp_image_url": ktp_image_url,
                "npwp_image_url": npwp_image_url,
                "ktp_data": ktp_result,
                "npwp_data": npwp_result
            }
        except Exception as e:
            print(f"Error fetching images and data: {e}")
            return {
                "ktp_image_url": None,
                "npwp_image_url": None,
                "ktp_data": None,
                "npwp_data": None
            }
        finally:
            conn.close()
    else:
        return {
            "ktp_image_url": None,
            "npwp_image_url": None,
            "ktp_data": None,
            "npwp_data": None
        }

@app.route('/images')
def images():
    """Displays images and data from ktp_data and npwp_data with search functionality."""
    search_query = request.args.get('search', '')
    results = fetch_images_and_data(search_query)
    return render_template('images.html', search_query=search_query, **results)

@app.route('/image/<int:id>')
def get_image(id):
    """Fetches an image from the database by its ID and returns it as a response."""
    conn = connect_to_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT scanned_image FROM ktp_data WHERE id = %s", (id,))
            image_data = cursor.fetchone()
            if image_data and image_data[0]:
                image = Image.open(io.BytesIO(image_data[0]))
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG')
                img_byte_arr = img_byte_arr.getvalue()
                return Response(img_byte_arr, mimetype='image/jpeg')
            else:
                return "Image not found"
        except Exception as e:
            print(f"Error fetching image: {e}")
            return "Error fetching image from the database"
        finally:
            conn.close()
    else:
        return "Database connection failed"

if __name__ == '__main__':
    app.run(debug=True)
