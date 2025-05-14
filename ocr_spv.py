from flask import Flask, render_template, Response, request
import psycopg2
import psycopg2.extras # Not strictly used here but often useful
import io
from PIL import Image # For image resizing and handling
import matplotlib
matplotlib.use('Agg') # Use a non-interactive backend for Matplotlib
import matplotlib.pyplot as plt
import base64
from io import BytesIO # For matplotlib charts and image streams
import fitz # PyMuPDF for PDF processing
import os # For checking static file if needed

# Initialize the Flask application
app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Jakarta83' # IMPORTANT: Use environment variables or secrets for production
}

# --- Helper Functions ---

def connect_to_db():
    """Establishes a connection to the database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return None

def add_values_on_bars(ax):
    """Adds value annotations on top of bars in a bar chart."""
    for bar in ax.patches:
        ax.annotate(format(bar.get_height(), '.0f'),
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha='center', va='bottom', xytext=(0, 5), textcoords='offset points')

def generate_charts():
    """Generates pie chart and bar charts for nama_petugas, provinsi, and kabupaten_kota distribution."""
    conn = connect_to_db()
    cursor = None
    if not conn:
        return None, None, None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nama_petugas, row_1 AS provinsi, row_2 AS kabupaten_kota 
            FROM ktp_data2 
            WHERE row_1 IS NOT NULL AND TRIM(row_1) <> '' AND 
                  row_2 IS NOT NULL AND TRIM(row_2) <> '' AND
                  nama_petugas IS NOT NULL AND TRIM(nama_petugas) <> ''
        """)
        data = cursor.fetchall()

        if not data:
            print("CHARTS: No sufficient data found for generating charts.")
            return None, None, None

        nama_petugas_count = {}
        provinsi_count = {}
        kabupaten_kota_count = {}

        for row in data:
            nama_petugas = row[0].strip() if row[0] else "Unknown"
            provinsi_raw = row[1].strip().upper() if row[1] else "Unknown"
            provinsi = provinsi_raw.replace("PROVINSI", "").strip()
            if not provinsi: provinsi = "Unknown"

            kabupaten_kota_raw = row[2].strip().upper() if row[2] else "Unknown"
            kabupaten_kota = kabupaten_kota_raw
            prefixes_to_remove = ["KABUPATEN ", "KOTA ADMINISTRASI ", "KOTA ", "KAB. ", "KAB ", "KOTAMADYA "]
            for prefix in prefixes_to_remove:
                if kabupaten_kota.startswith(prefix):
                    kabupaten_kota = kabupaten_kota[len(prefix):].strip()
                    break
            if not kabupaten_kota: kabupaten_kota = "Unknown"

            nama_petugas_count[nama_petugas] = nama_petugas_count.get(nama_petugas, 0) + 1
            provinsi_count[provinsi] = provinsi_count.get(provinsi, 0) + 1
            kabupaten_kota_count[kabupaten_kota] = kabupaten_kota_count.get(kabupaten_kota, 0) + 1
        
        if not nama_petugas_count: # Check again after processing
            print("CHARTS: No data after processing for charts.")
            return None, None, None

        # Pie Chart for Petugas
        fig0, ax0 = plt.subplots(figsize=(8, 8)) # Ensure it's large enough
        ax0.pie(nama_petugas_count.values(), labels=nama_petugas_count.keys(), autopct='%1.1f%%', startangle=90)
        ax0.axis('equal')
        ax0.set_title('Distribusi Dokumen oleh Petugas', pad=20)
        pie_img_buffer = BytesIO()
        plt.savefig(pie_img_buffer, format='png', bbox_inches='tight')
        pie_img_buffer.seek(0)
        pie_chart_url = base64.b64encode(pie_img_buffer.getvalue()).decode('utf-8')
        plt.close(fig0)

        # Bar Chart for Provinsi
        sorted_provinsi = dict(sorted(provinsi_count.items(), key=lambda item: item[1], reverse=True))
        fig1, ax1 = plt.subplots(figsize=(15, 15))
        ax1.barh(list(sorted_provinsi.keys()), list(sorted_provinsi.values()), color='skyblue')
        ax1.set_title('Distribusi berdasarkan Provinsi', fontsize=30)
        ax1.set_xlabel('Jumlah', fontsize=20)  # Ubah label sumbu X ke "Jumlah"
        ax1.set_ylabel('Provinsi', fontsize=20)  # Ubah label sumbu Y ke "Provinsi"
        plt.xticks(rotation=0, ha="right", fontsize=20)
        add_values_on_bars(ax1)
        plt.tight_layout()
        bar_provinsi_img_buffer = BytesIO()
        plt.savefig(bar_provinsi_img_buffer, format='png')
        bar_provinsi_img_buffer.seek(0)
        bar_provinsi_chart_url = base64.b64encode(bar_provinsi_img_buffer.getvalue()).decode('utf-8')
        plt.close(fig1)

        # Bar Chart for Kabupaten/Kota
        sorted_kabupaten = dict(sorted(kabupaten_kota_count.items(), key=lambda item: item[1], reverse=True))
        fig2, ax2 = plt.subplots(figsize=(15, 15))
        ax2.barh(list(sorted_kabupaten.keys()), list(sorted_kabupaten.values()), color='lightcoral')
        ax2.set_title('Distribusi berdasarkan Kabupaten/Kota', fontsize=30)
        ax2.set_xlabel('Jumlah', fontsize=20)
        ax2.set_ylabel('Kabupaten/Kota', fontsize=20)
        plt.xticks(rotation=0, ha="right", fontsize=20)
        add_values_on_bars(ax2)
        plt.tight_layout()
        bar_kabupaten_img_buffer = BytesIO()
        plt.savefig(bar_kabupaten_img_buffer, format='png')
        bar_kabupaten_img_buffer.seek(0)
        bar_kabupaten_chart_url = base64.b64encode(bar_kabupaten_img_buffer.getvalue()).decode('utf-8')
        plt.close(fig2)

        return pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url
    except Exception as e:
        print(f"CHARTS ERROR: Error generating charts: {e}")
        return None, None, None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def convert_pdf_page_to_image_bytes(pdf_bytes, page_number=0, dpi=150, output_image_format="png"):
    """Converts a specific page of a PDF (from bytes) to image bytes."""
    if not pdf_bytes:
        print("PDF CONVERSION: No PDF bytes provided.")
        return None
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        if not len(pdf_document):
            print("PDF CONVERSION: PDF has no pages.")
            pdf_document.close()
            return None

        actual_page_number = max(0, min(page_number, len(pdf_document) - 1))

        page = pdf_document.load_page(actual_page_number)
        pixmap = page.get_pixmap(dpi=dpi)
        image_bytes = pixmap.tobytes(output=output_image_format.lower())
        pdf_document.close()
        print(f"PDF CONVERSION: Successfully converted page {actual_page_number} to {output_image_format.upper()}.")
        return image_bytes
    except Exception as e:
        print(f"PDF CONVERSION ERROR: {e}")
        return None

def prepare_image_for_frontend(original_bytes, target_size=(350, 200), final_output_format='PNG'):
    """
    If original_bytes is a PDF, converts its first page to an image.
    Then, resizes the (converted or original) image, and encodes to base64.
    Uses Pillow's thumbnail method to maintain aspect ratio.
    """
    if not original_bytes:
        print("PREPARE IMAGE: original_bytes is None.")
        return None
    
    print(f"PREPARE IMAGE: Received {len(original_bytes)} bytes. Target format: {final_output_format}.")
    image_bytes_to_process = None

    # Attempt PDF conversion (first page, higher DPI for initial render before thumbnail)
    converted_from_pdf = convert_pdf_page_to_image_bytes(original_bytes, page_number=0, dpi=200, output_image_format="png")

    if converted_from_pdf:
        image_bytes_to_process = converted_from_pdf
    else:
        print("PREPARE IMAGE: Assuming input is already an image format (PDF conversion failed or not a PDF).")
        image_bytes_to_process = original_bytes

    if not image_bytes_to_process:
        print("PREPARE IMAGE: No image bytes to process after PDF check.")
        return None

    try:
        img_io = io.BytesIO(image_bytes_to_process)
        img = Image.open(img_io)
        
        # Ensure image is in RGB or RGBA mode if saving as JPEG, or just L (grayscale) or RGB/RGBA for PNG
        if final_output_format.upper() == 'JPEG' and img.mode not in ('RGB', 'L'):
            print(f"PREPARE IMAGE: Converting image mode from {img.mode} to RGB for JPEG saving.")
            img = img.convert('RGB')
        elif final_output_format.upper() == 'PNG' and img.mode == 'CMYK': # PNG doesn't directly support CMYK well in PIL for web
            print(f"PREPARE IMAGE: Converting image mode from CMYK to RGBA for PNG saving.")
            img = img.convert('RGBA')


        original_format = img.format # Store original format if available
        print(f"PREPARE IMAGE: Opened image. Original format (if known): {original_format}, Mode: {img.mode}")

        img.thumbnail(target_size, Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        print(f"PREPARE IMAGE: Resized to fit within {target_size}. New size: {img.size}")

        output_io = io.BytesIO()
        if final_output_format.upper() == 'JPEG':
            img.save(output_io, format=final_output_format, quality=85) # Add quality for JPEG
        else: # PNG
            img.save(output_io, format=final_output_format)
        
        encoded_image_bytes = base64.b64encode(output_io.getvalue()).decode('utf-8')
        print(f"PREPARE IMAGE: Successfully processed and encoded image to base64 ({final_output_format}).")
        return encoded_image_bytes
    except Exception as e:
        print(f"PREPARE IMAGE ERROR: Error resizing/encoding image: {e}")
        return None


@app.route('/qc-process')
def qc_process():
    search_query = request.args.get('search', '').strip()
    ktp_image_url, npwp_image_url, form_data3_image_url = None, None, None
    ktp_data2, npwp_data2, form_data3_data = None, None, None
    error_message = None

    print(f"\nQC PROCESS: Search query received: '{search_query}'")

    if not search_query:
        error_message = "Please enter a Nomor Input to search."
        return render_template(
            'qc_process.html', search_query=search_query,
            ktp_image_url=None, npwp_image_url=None, form_data3_image_url=None,
            ktp_data2=None, npwp_data2=None, form_data3_data=None,
            error_message=error_message
        )

    conn = connect_to_db()
    cursor = None
    if not conn:
        error_message = "Database connection failed."
    else:
        try:
            cursor = conn.cursor()
            ktp_npwp_preview_size = (450, 280)
            form_preview_size = (600, 850)
            output_image_type = 'PNG' # Use PNG for clearer text on scanned docs

            # Fetch KTP image and data
            print("QC PROCESS: Fetching KTP data...")
            cursor.execute(
                """SELECT scanned_image, nama_petugas, nomor_input, row_1, row_2, row_4, row_6, row_8
                   FROM ktp_data2 WHERE nomor_input = %s LIMIT 1""", (search_query,)
            )
            ktp_result = cursor.fetchone()
            if ktp_result:
                print("QC PROCESS: KTP result found.")
                if ktp_result[0]:
                    print("QC PROCESS: KTP scanned_image found, preparing for frontend...")
                    ktp_image_url = prepare_image_for_frontend(ktp_result[0], ktp_npwp_preview_size, final_output_format=output_image_type)
                else:
                    print("QC PROCESS: KTP scanned_image is NULL.")
                ktp_data2 = {
                    'nama_petugas': ktp_result[1], 'nomor_input': ktp_result[2],
                    'provinsi': ktp_result[3], 'kabupaten_kota': ktp_result[4],
                    'nik': ktp_result[5], 'nama': ktp_result[6], 'dob': ktp_result[7]
                }
            else:
                print("QC PROCESS: No KTP result found for this nomor_input.")

            # Fetch NPWP image and data
            print("QC PROCESS: Fetching NPWP data...")
            cursor.execute(
                """SELECT scanned_image, nama_petugas, nomor_input, row_2, row_4, row_5, row_7
                   FROM npwp_data2 WHERE nomor_input = %s LIMIT 1""", (search_query,)
            )
            npwp_result = cursor.fetchone()
            if npwp_result:
                print("QC PROCESS: NPWP result found.")
                if npwp_result[0]:
                    print("QC PROCESS: NPWP scanned_image found, preparing for frontend...")
                    npwp_image_url = prepare_image_for_frontend(npwp_result[0], ktp_npwp_preview_size, final_output_format=output_image_type)
                else:
                    print("QC PROCESS: NPWP scanned_image is NULL.")
                npwp_data2 = {
                    'nama_petugas': npwp_result[1], 'nomor_input': npwp_result[2],
                    'dirjen_pajak': npwp_result[3], 'npwp': npwp_result[4],
                    'nik': npwp_result[5], 'nama': npwp_result[6]
                }
            else:
                print("QC PROCESS: No NPWP result found for this nomor_input.")
            
            # Fetch Form (form_data3) image and data
            print("QC PROCESS: Fetching Form (form_data3) data...")
            form_data3_sql_query = """
                SELECT scanned_image, nama_petugas, nomor_input, 
                       kartu_yang_dipilih, cobrand, nama_pemberi_referensi, nik,
                       nomor_kartu_mnc_bank, kode_cabang, nama_cabang_capem,
                       nama_lengkap_ktp_paspor, nama_yang_dicetak_pada_kartu, nomor_ktp,
                       jenis_kelamin, tempat_lahir, tanggal_lahir, status_perkawinan,
                       jumlah_tanggungan, pendidikan, nama_universitas, email,
                       nama_ibu_kandung
                FROM form_data3 
                WHERE nomor_input = %s LIMIT 1
            """
            cursor.execute(form_data3_sql_query, (search_query,))
            form_result = cursor.fetchone()

            if form_result:
                print("QC PROCESS: Form (form_data3) result found.")
                if form_result[0]:
                    print("QC PROCESS: Form scanned_image found, preparing for frontend...")
                    form_data3_image_url = prepare_image_for_frontend(form_result[0], form_preview_size, final_output_format=output_image_type)
                else:
                    print("QC PROCESS: Form scanned_image is NULL.")
                form_data3_data = {
                    'nama_petugas': form_result[1], 'nomor_input': form_result[2],
                    'kartu_yang_dipilih': form_result[3], 'cobrand': form_result[4],
                    'nama_pemberi_referensi': form_result[5], 'nik': form_result[6],
                    'nomor_kartu_mnc_bank': form_result[7], 'kode_cabang': form_result[8],
                    'nama_cabang_capem': form_result[9], 'nama_lengkap_ktp_paspor': form_result[10],
                    'nama_yang_dicetak_pada_kartu': form_result[11], 'nomor_ktp': form_result[12],
                    'jenis_kelamin': form_result[13], 'tempat_lahir': form_result[14],
                    'tanggal_lahir': form_result[15].strftime('%Y-%m-%d') if form_result[15] else None,
                    'status_perkawinan': form_result[16], 'jumlah_tanggungan': form_result[17],
                    'pendidikan': form_result[18], 'nama_universitas': form_result[19],
                    'email': form_result[20], 'nama_ibu_kandung': form_result[21]
                }
            else:
                print("QC PROCESS: No Form (form_data3) result found for this nomor_input.")
            
            if not ktp_result and not npwp_result and not form_result:
                 error_message = f"No data found for Nomor Input: '{search_query}'."

        except psycopg2.Error as db_err:
            error_message = f"Database error: {db_err}"
            print(f"QC PROCESS DATABASE ERROR: {db_err}")
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"QC PROCESS UNEXPECTED ERROR: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    print(f"QC PROCESS: Rendering template. KTP URL: {bool(ktp_image_url)}, NPWP URL: {bool(npwp_image_url)}, Form URL: {bool(form_data3_image_url)}")
    return render_template(
        'qc_process.html',
        search_query=search_query,
        ktp_image_url=ktp_image_url,
        npwp_image_url=npwp_image_url,
        form_data3_image_url=form_data3_image_url,
        ktp_data2=ktp_data2,
        npwp_data2=npwp_data2,
        form_data3_data=form_data3_data,
        error_message=error_message
    )


@app.route('/')
def index():
    conn = connect_to_db()
    cursor = None
    if not conn:
        return "Database connection failed for index page."
    
    total_register, total_unique_provinces, total_unique_kabupaten = 0, 0, 0
    user_data, data_table_rows = [], []
    pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url = None, None, None
    search_query = request.args.get('search', '').strip()

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ktp_data2")
        total_register = (cursor.fetchone() or [0])[0]

        cursor.execute("SELECT COUNT(DISTINCT TRIM(UPPER(row_1))) FROM ktp_data2 WHERE row_1 IS NOT NULL AND TRIM(row_1) != ''")
        total_unique_provinces = (cursor.fetchone() or [0])[0]

        cursor.execute("SELECT COUNT(DISTINCT TRIM(UPPER(row_2))) FROM ktp_data2 WHERE row_2 IS NOT NULL AND TRIM(row_2) != ''")
        total_unique_kabupaten = (cursor.fetchone() or [0])[0]
        
        cursor.execute("SELECT username, last_login FROM users ORDER BY last_login DESC NULLS LAST")
        user_data = cursor.fetchall()

        base_query_data_table = """SELECT id, nama_petugas, row_1 AS Provinsi, row_2 AS Kabupaten_Kota,
                                 row_4 AS NIK, row_6 AS Nama, row_8 AS DOB, nomor_input
                                 FROM ktp_data2"""
        query_params = []
        if search_query:
            base_query_data_table += " WHERE nama_petugas ILIKE %s OR nomor_input ILIKE %s OR row_6 ILIKE %s OR row_4 ILIKE %s"
            search_like = f"%{search_query}%"
            query_params.extend([search_like, search_like, search_like, search_like])
        
        base_query_data_table += " ORDER BY id DESC LIMIT 100"
        cursor.execute(base_query_data_table, query_params if query_params else None)
        data_table_rows_raw = cursor.fetchall()
        # Get column names for the table header
        colnames = [desc[0] for desc in cursor.description]
        data_table_rows = [dict(zip(colnames, row)) for row in data_table_rows_raw]


        pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url = generate_charts()

    except psycopg2.Error as e:
        print(f"INDEX PAGE DB ERROR: {e}")
        return f"PostgreSQL Error on Index Page: {e}"
    except Exception as e:
        print(f"INDEX PAGE ERROR: {e}")
        return f"Error fetching data for Index Page: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return render_template(
        'index.html',
        total_register=total_register,
        total_unique_provinces=total_unique_provinces,
        total_unique_kabupaten=total_unique_kabupaten,
        pie_chart_url=pie_chart_url,
        bar_provinsi_chart_url=bar_provinsi_chart_url,
        bar_kabupaten_chart_url=bar_kabupaten_chart_url,
        search_query=search_query,
        data_table_header=colnames if 'colnames' in locals() else [],
        data_table_rows=data_table_rows,
        user_data=user_data,
    )

# This direct image route might be less used if all images are embedded, but good for testing.
@app.route('/image_direct/<doc_type>/<nomor_input_str>')
def get_image_direct(doc_type, nomor_input_str):
    """Serves an image directly. If stored as PDF, converts first page to PNG."""
    conn = connect_to_db()
    cursor = None
    if not conn: return "Database connection failed", 503
    
    try:
        cursor = conn.cursor()
        table_map = {'ktp': 'ktp_data2', 'npwp': 'npwp_data2', 'form': 'form_data3'}
        table_name = table_map.get(doc_type.lower())
        if not table_name: return "Invalid document type", 400

        cursor.execute(f"SELECT scanned_image FROM {table_name} WHERE nomor_input = %s LIMIT 1", (nomor_input_str,))
        db_row = cursor.fetchone()

        if db_row and db_row[0]:
            original_bytes = db_row[0]
            image_to_serve_bytes = None
            mimetype = 'image/png' # Defaulting to PNG as PDF conversion outputs PNG

            converted_image = convert_pdf_page_to_image_bytes(original_bytes, output_image_format="png", dpi=150)
            if converted_image:
                image_to_serve_bytes = converted_image
            else: # If PDF conversion failed, try to serve original assuming it's an image
                print(f"DIRECT IMAGE: PDF conversion failed for {doc_type}/{nomor_input_str}. Attempting to serve original bytes.")
                image_to_serve_bytes = original_bytes
                # Try to infer mimetype if not PDF (this is a basic attempt)
                try:
                    temp_img = Image.open(io.BytesIO(original_bytes))
                    inferred_mime = Image.MIME.get(temp_img.format.upper())
                    if inferred_mime: mimetype = inferred_mime
                    print(f"DIRECT IMAGE: Inferred MIME type: {mimetype}")
                except Exception as e_mime:
                    print(f"DIRECT IMAGE: Could not infer MIME type from original bytes: {e_mime}. Defaulting to application/octet-stream.")
                    mimetype = 'application/octet-stream' # Fallback if cannot determine type

            if image_to_serve_bytes:
                return Response(image_to_serve_bytes, mimetype=mimetype)
            else:
                return "Error processing stored document for display.", 500
        else:
            return "Document not found", 404
    except Exception as e:
        print(f"DIRECT IMAGE ERROR for {doc_type}/{nomor_input_str}: {e}")
        return "Error fetching document from database", 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    # Check if static folder and magnifying glass image exist (optional)
    static_folder = os.path.join(app.root_path, 'static')
    magnifying_glass_path = os.path.join(static_folder, 'magnifying-glass.png')
    if not os.path.exists(magnifying_glass_path):
        print(f"WARNING: Magnifying glass image not found at {magnifying_glass_path}. Zoom feature might not show icon.")
    
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)