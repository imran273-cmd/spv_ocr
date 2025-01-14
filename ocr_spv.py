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

def add_values_on_bars(ax):
    """Adds value annotations on top of bars in a bar chart."""
    for bar in ax.patches:
        ax.annotate(format(bar.get_height(), '.0f'), 
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha='center', va='bottom')

def generate_charts():
    """Generates pie chart and bar charts for nama_petugas, provinsi, and kabupaten_kota distribution."""
    conn = connect_to_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT nama_petugas, row_1 AS provinsi, row_2 AS kabupaten_kota FROM ktp_data2")
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
            fig0, ax0 = plt.subplots()
            ax0.pie(nama_petugas_count.values(), labels=nama_petugas_count.keys(), autopct='%1.1f%%')
            ax0.set_title('Distribusi Dokumen')
            pie_img = BytesIO()
            plt.savefig(pie_img, format='png')
            pie_img.seek(0)
            pie_chart_url = base64.b64encode(pie_img.getvalue()).decode('utf-8')
            plt.close(fig0)

            # Generate bar chart for provinsi
            fig1, ax1 = plt.subplots(figsize=(15, 6))
            ax1.bar(provinsi_count.keys(), provinsi_count.values())
            ax1.set_title('Distribution by Provinsi')
            ax1.set_xlabel('Provinsi')
            ax1.set_ylabel('Count')
            add_values_on_bars(ax1)
            bar_provinsi_img = BytesIO()
            plt.savefig(bar_provinsi_img, format='png')
            bar_provinsi_img.seek(0)
            bar_provinsi_chart_url = base64.b64encode(bar_provinsi_img.getvalue()).decode('utf-8')
            plt.close(fig1)

            # Generate bar chart for kabupaten_kota
            fig2, ax2 = plt.subplots(figsize=(15, 6))
            ax2.bar(kabupaten_kota_count.keys(), kabupaten_kota_count.values())
            ax2.set_title('Distribution by Kabupaten/Kota')
            ax2.set_xlabel('Kabupaten/Kota')
            ax2.set_ylabel('Count')
            add_values_on_bars(ax2)
            bar_kabupaten_img = BytesIO()
            plt.savefig(bar_kabupaten_img, format='png')
            bar_kabupaten_img.seek(0)
            bar_kabupaten_chart_url = base64.b64encode(bar_kabupaten_img.getvalue()).decode('utf-8')
            plt.close(fig2)

            return pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url
        except Exception as e:
            print(f"Error generating charts: {e}")
            return None, None, None
        finally:
            conn.close()
    else:
        return None, None, None

@app.route('/qc-process')
def qc_process():
    """Displays QC Process images and data based on search by nomor_input."""
    conn = connect_to_db()
    if conn:
        try:
            # Get search query from request
            search_query = request.args.get('search', '').strip()

            # If no search query is provided, render the page with an empty state
            if not search_query:
                return render_template(
                    'qc_process.html',
                    search_query='',
                    ktp_image_url=None,
                    npwp_image_url=None,
                    form_image_url=None,
                    ktp_data2=None,
                    npwp_data=None,
                    form_data=None
                )

            cursor = conn.cursor()

            # Fetch KTP image and data by nomor_input
            cursor.execute(
                """SELECT scanned_image, nama_petugas, nomor_input, row_1, row_2, row_4, row_6, row_8 
                   FROM ktp_data2 WHERE nomor_input = %s LIMIT 1""",
                (search_query,)
            )
            ktp_result = cursor.fetchone()
            if ktp_result and ktp_result[0]:
                ktp_image_url = base64.b64encode(ktp_result[0]).decode('utf-8')
                ktp_data2 = ktp_result[1:]  # Additional data columns from KTP
            else:
                ktp_image_url = None
                ktp_data2 = None

            # Fetch NPWP image and data by nomor_input
            cursor.execute(
                """SELECT scanned_image, nama_petugas, nomor_input, row_2, row_4, row_5, row_7 
                   FROM npwp_data2 WHERE nomor_input = %s LIMIT 1""",
                (search_query,)
            )
            npwp_result = cursor.fetchone()
            if npwp_result and npwp_result[0]:
                npwp_image_url = base64.b64encode(npwp_result[0]).decode('utf-8')
                npwp_data = npwp_result[1:]  # Additional data columns from NPWP
            else:
                npwp_image_url = None
                npwp_data = None

            # Fetch Form image and additional data from form_data2 by nomor_input
            cursor.execute(
                """SELECT scanned_image, nama_petugas, kartu_yang_dipilih, nama_pemberi_referensi, kode_cabang, 
                          nama_cabang_capem, nama_lengkap_sesuai_ktp_paspor, nama_yang_dicetak_pada_kartu, nomor_ktp 
                   FROM form_data2 WHERE nomor_input = %s LIMIT 1""",
                (search_query,)
            )
            form_result = cursor.fetchone()
            if form_result and form_result[0]:
                form_image_url = base64.b64encode(form_result[0]).decode('utf-8')
                form_data = form_result[1:]  # Additional data columns from Form
            else:
                form_image_url = None
                form_data = None

            # Debug logs to ensure data is fetched correctly
            print(f"Search Query: {search_query}")
            print(f"KTP Result: {ktp_result}")
            print(f"NPWP Result: {npwp_result}")
            print(f"Form Result: {form_result}")

            # Return the rendered template with the fetched data
            return render_template(
                'qc_process.html',
                search_query=search_query,
                ktp_image_url=ktp_image_url,
                npwp_image_url=npwp_image_url,
                form_image_url=form_image_url,
                ktp_data2=ktp_data2,
                npwp_data=npwp_data,
                form_data=form_data
            )
        except Exception as e:
            print(f"Error fetching QC Process data: {e}")
            return f"Error fetching QC Process data: {e}"
        finally:
            conn.close()
    else:
        return "Database connection failed"

@app.route('/')
def index():
    """Displays the Executive Summary, Data Table, and QC Process tabs with insights."""
    conn = connect_to_db()
    if conn:
        try:
            cursor = conn.cursor()

            # Fetch total register
            cursor.execute("SELECT COUNT(*) FROM ktp_data2")
            total_register = cursor.fetchone()[0]

            # Fetch total unique provinces
            cursor.execute("SELECT COUNT(DISTINCT row_1) FROM ktp_data2")
            total_unique_provinces = cursor.fetchone()[0]

            # Fetch total unique kabupaten/kota
            cursor.execute("SELECT COUNT(DISTINCT row_2) FROM ktp_data2")
            total_unique_kabupaten = cursor.fetchone()[0]

            # Fetch user data (users' names and login times), ordered by login time (latest first)
            cursor.execute("SELECT username, last_login FROM users ORDER BY last_login DESC")
            user_data = cursor.fetchall()

            # Handle search query for the Data Table tab
            search_query = request.args.get('search', '').strip()
            if search_query:
                cursor.execute(
                    """SELECT nama_petugas, row_1 AS Provinsi, row_2 AS Kabupaten_Kota, 
                              row_4 AS NIK, row_6 AS Nama, row_8 AS DOB, nomor_input 
                       FROM ktp_data2 WHERE nama_petugas ILIKE %s""",
                    (f"%{search_query}%",)
                )
            else:
                cursor.execute(
                    """SELECT nama_petugas, row_1 AS Provinsi, row_2 AS Kabupaten_Kota, 
                              row_4 AS NIK, row_6 AS Nama, row_8 AS DOB, nomor_input 
                       FROM ktp_data2"""
                )
            data = cursor.fetchall()

            # Generate charts
            pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url = generate_charts()

            # Render the index template
            return render_template(
                'index.html',
                total_register=total_register,
                total_unique_provinces=total_unique_provinces,
                total_unique_kabupaten=total_unique_kabupaten,
                pie_chart_url=pie_chart_url,
                bar_provinsi_chart_url=bar_provinsi_chart_url,
                bar_kabupaten_chart_url=bar_kabupaten_chart_url,
                search_query=search_query,
                data=data,
                user_data=user_data,  # Pass the sorted user data to the template
            )
        except psycopg2.Error as e:
            print(f"PostgreSQL Error: {e}")
            return f"PostgreSQL Error: {e}"
        except Exception as e:
            print(f"Error fetching data: {e}")
            return f"Error fetching data: {e}"
        finally:
            conn.close()
    else:
        return "Database connection failed"


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