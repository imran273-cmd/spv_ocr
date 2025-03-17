from flask import Flask, render_template, Response, request, redirect, url_for
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
                # Clean the provinsi by removing "PROVINSI" (case-insensitive)
                provinsi = row[1].replace("PROVINSI", "").strip() if row[1] else ""
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

@app.route('/qc-process', methods=['GET', 'POST'])
def qc_process():
    """Displays QC Process images and data based on search by nomor_input and allows data editing."""
    conn = connect_to_db()
    if conn:
        try:
            search_query = request.args.get('search', '').strip()
            message = None

            if request.method == 'POST':
                # Get data from the form
                table_name = request.form.get('table_name')
                nomor_input = request.form.get('nomor_input')

                if table_name and nomor_input:
                    cursor = conn.cursor()  # Get cursor *within* the POST handling

                    if table_name == 'ktp_data2':
                        provinsi = request.form.get('provinsi')
                        kabupaten_kota = request.form.get('kabupaten_kota')
                        nik = request.form.get('nik')
                        nama = request.form.get('nama')
                        dob = request.form.get('dob')

                        cursor.execute(
                            """UPDATE ktp_data2 SET row_1 = %s, row_2 = %s, row_4 = %s, row_6 = %s, row_8 = %s
                               WHERE nomor_input = %s""",
                            (provinsi, kabupaten_kota, nik, nama, dob, nomor_input)
                        )
                        message = "KTP data updated successfully!"

                    elif table_name == 'npwp_data2':
                        dirjen_pajak = request.form.get('dirjen_pajak')
                        npwp = request.form.get('npwp')
                        nik_npwp = request.form.get('nik_npwp')
                        nama_npwp = request.form.get('nama_npwp')

                        cursor.execute(
                            """UPDATE npwp_data2 SET row_2 = %s, row_4 = %s, row_5 = %s, row_7 = %s
                               WHERE nomor_input = %s""",
                            (dirjen_pajak, npwp, nik_npwp, nama_npwp, nomor_input)
                        )
                        message = "NPWP data updated successfully!"

                    elif table_name == 'form_data3':
                        kartu_yang_dipilih = request.form.get('kartu_yang_dipilih')
                        cobrand = request.form.get('cobrand')
                        kode_cabang = request.form.get('kode_cabang')
                        nama_cabang_capem = request.form.get('nama_cabang_capem')
                        nama_lengkap_ktp_paspor = request.form.get('nama_lengkap_ktp_paspor')
                        nama_yang_dicetak_pada_kartu = request.form.get('nama_yang_dicetak_pada_kartu')

                        cursor.execute(
                            """UPDATE form_data3 SET kartu_yang_dipilih = %s, cobrand = %s, kode_cabang = %s,
                               nama_cabang_capem = %s, nama_lengkap_ktp_paspor = %s, nama_yang_dicetak_pada_kartu = %s
                               WHERE nomor_input = %s""",
                            (kartu_yang_dipilih, cobrand, kode_cabang, nama_cabang_capem, nama_lengkap_ktp_paspor,
                             nama_yang_dicetak_pada_kartu, nomor_input)
                        )
                        message = "Form data updated successfully!"
                    else:
                        message = "Invalid table name."

                    conn.commit()  # Commit changes *after* the correct execution
                    search_query = nomor_input  # Reload the data with the same nomor_input
                else:
                    message = "Table name or Nomor Input is missing."

            # Fetch data (This part runs for both GET and after POST)
            cursor = conn.cursor()  # Get cursor for fetching
            ktp_data, npwp_data, form_data = None, None, None  # Initialize
            ktp_image_url, npwp_image_url, form_image_url = None, None, None

            if search_query:  # Only fetch if there's a search query
                # Fetch KTP image and data by nomor_input
                cursor.execute(
                    """SELECT scanned_image, nama_petugas, nomor_input, row_1, row_2, row_4, row_6, row_8
                       FROM ktp_data2 WHERE nomor_input = %s LIMIT 1""",
                    (search_query,)
                )
                ktp_result = cursor.fetchone()
                if ktp_result and ktp_result[0]:
                    ktp_image_url = base64.b64encode(ktp_result[0]).decode('utf-8')
                    ktp_data = {
                        'nama_petugas': ktp_result[1],
                        'nomor_input': ktp_result[2],
                        'provinsi': ktp_result[3],
                        'kabupaten_kota': ktp_result[4],
                        'nik': ktp_result[5],
                        'nama': ktp_result[6],
                        'dob': ktp_result[7]
                    }

                # Fetch NPWP image and data
                cursor.execute(
                    """SELECT scanned_image, nama_petugas, nomor_input, row_2, row_4, row_5, row_7
                       FROM npwp_data2 WHERE nomor_input = %s LIMIT 1""",
                    (search_query,)
                )
                npwp_result = cursor.fetchone()
                if npwp_result and npwp_result[0]:
                    npwp_image_url = base64.b64encode(npwp_result[0]).decode('utf-8')
                    npwp_data = {
                        'nama_petugas': npwp_result[1],
                        'nomor_input': npwp_result[2],
                        'dirjen_pajak': npwp_result[3],
                        'npwp': npwp_result[4],
                        'nik': npwp_result[5],
                        'nama': npwp_result[6]
                    }

                # Fetch Form image and data
                cursor.execute(
                    """SELECT scanned_image, nama_petugas, nomor_input, kartu_yang_dipilih, cobrand, kode_cabang,
                           nama_cabang_capem, nama_lengkap_ktp_paspor, nama_yang_dicetak_pada_kartu
                       FROM form_data3 WHERE nomor_input = %s LIMIT 1""",
                    (search_query,)
                )
                form_result = cursor.fetchone()
                if form_result and form_result[0]:
                    form_image_url = base64.b64encode(form_result[0]).decode('utf-8')
                    form_data = {
                        'nama_petugas': form_result[1],
                        'nomor_input': form_result[2],
                        'kartu_yang_dipilih': form_result[3],
                        'cobrand': form_result[4],
                        'kode_cabang': form_result[5],
                        'nama_cabang_capem': form_result[6],
                        'nama_lengkap_ktp_paspor': form_result[7],
                        'nama_yang_dicetak_pada_kartu': form_result[8]
                    }

            # Render the template
            return render_template(
                'qc_process.html',
                search_query=search_query,
                ktp_image_url=ktp_image_url,
                npwp_image_url=npwp_image_url,
                form_image_url=form_image_url,
                ktp_data=ktp_data,
                npwp_data=npwp_data,
                form_data=form_data,
                message=message
            )

        except Exception as e:
            print(f"Error in qc_process: {e}")
            return f"Error in qc_process: {e}"
        finally:
            if conn:
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

@app.route('/qc-process/edit/<int:id>', methods=['GET', 'POST'])
def edit_qc_process(id):
    """Handles the editing of QC Process data by ID."""
    conn = connect_to_db()
    if conn:
        try:
            cursor = conn.cursor()

            # Handle form submission for data update
            if request.method == 'POST':
                # Retrieve data from the form
                nama_petugas = request.form['nama_petugas']
                nomor_input = request.form['nomor_input']
                provinsi = request.form['provinsi']
                kabupaten_kota = request.form['kabupaten_kota']
                nik = request.form['nik']
                nama = request.form['nama']
                dob = request.form['dob']

                # Update data in the database (example for ktp_data2, similar can be done for npwp_data2 and form_data3)
                cursor.execute("""
                    UPDATE ktp_data2 
                    SET nama_petugas = %s, row_1 = %s, row_2 = %s, row_4 = %s, row_6 = %s, row_8 = %s
                    WHERE nomor_input = %s
                """, (nama_petugas, provinsi, kabupaten_kota, nik, nama, dob, nomor_input))
                conn.commit()

                return redirect(f'/qc-process?search={nomor_input}')  # Redirect back to search results after update

            # Fetch data by ID for editing
            cursor.execute("""
                SELECT scanned_image, nama_petugas, nomor_input, row_1, row_2, row_4, row_6, row_8 
                FROM ktp_data2 WHERE nomor_input = %s LIMIT 1
            """, (id,))
            ktp_result = cursor.fetchone()

            if ktp_result:
                ktp_data = ktp_result[1:]  # Exclude image data for editing
            else:
                ktp_data = None

            # Return the edit form with the current data
            return render_template('edit_qc_process.html', ktp_data=ktp_data, id=id)

        except Exception as e:
            print(f"Error editing QC Process data: {e}")
            return f"Error editing QC Process data: {e}"
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
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)