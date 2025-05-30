from flask import Flask, render_template, Response, request
import psycopg2
import psycopg2.extras
import io
from PIL import Image, UnidentifiedImageError
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import fitz # PyMuPDF
import os

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Jakarta83'
}

def connect_to_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return None

def add_values_on_horizontal_bars(ax, fontsize=10):
    for bar in ax.patches:
        ax.annotate(format(bar.get_width(), '.0f'),
                    (bar.get_width(), bar.get_y() + bar.get_height() / 2.),
                    ha='left', va='center',
                    xytext=(5, 0),
                    textcoords='offset points',
                    fontsize=fontsize)

def generate_charts():
    # ... (generate_charts code remains largely the same, no direct image processing here) ...
    # For brevity, I'll keep it as is from your original if no changes are needed for this problem
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
        ax0.pie(nama_petugas_count.values(), labels=nama_petugas_count.keys(), autopct='%1.1f%%', startangle=90, textprops={'fontsize': 10}) # Can adjust label font size here too
        ax0.axis('equal')
        ax0.set_title('Distribusi Dokumen oleh Petugas', pad=20, fontsize=16)
        pie_img_buffer = BytesIO()
        plt.savefig(pie_img_buffer, format='png', bbox_inches='tight')
        pie_img_buffer.seek(0)
        pie_chart_url = base64.b64encode(pie_img_buffer.getvalue()).decode('utf-8')
        plt.close(fig0)

        # Bar Chart for Provinsi
        sorted_provinsi = dict(sorted(provinsi_count.items(), key=lambda item: item[1], reverse=True))
        fig1, ax1 = plt.subplots(figsize=(10, max(8, len(sorted_provinsi) * 0.5))) # Dynamic height
        ax1.barh(list(sorted_provinsi.keys()), list(sorted_provinsi.values()), color='skyblue')
        ax1.set_title('Distribusi berdasarkan Provinsi', fontsize=20)
        ax1.set_xlabel('Jumlah', fontsize=16)
        ax1.set_ylabel('Provinsi', fontsize=16)
        ax1.tick_params(axis='x', labelsize=14)
        ax1.tick_params(axis='y', labelsize=14)
        ax1.invert_yaxis()
        add_values_on_horizontal_bars(ax1, fontsize=12)
        plt.tight_layout()
        bar_provinsi_img_buffer = BytesIO()
        plt.savefig(bar_provinsi_img_buffer, format='png', bbox_inches='tight')
        bar_provinsi_img_buffer.seek(0)
        bar_provinsi_chart_url = base64.b64encode(bar_provinsi_img_buffer.getvalue()).decode('utf-8')
        plt.close(fig1)

        # Bar Chart for Kabupaten/Kota
        top_n_kabupaten = 30
        sorted_kabupaten_items = sorted(kabupaten_kota_count.items(), key=lambda item: item[1], reverse=True)
        num_known_kabupaten = len([k for k,v in sorted_kabupaten_items if k != "Unknown"])

        if num_known_kabupaten > top_n_kabupaten:
            top_kabupaten = dict(sorted_kabupaten_items[:top_n_kabupaten])
            others_count = sum(v for k,v in sorted_kabupaten_items[top_n_kabupaten:])
            if others_count > 0:
                top_kabupaten["Lainnya"] = top_kabupaten.get("Lainnya", 0) + others_count
            if "Unknown" in kabupaten_kota_count and "Unknown" not in top_kabupaten:
                 is_unknown_in_others = any(item[0] == "Unknown" for item in sorted_kabupaten_items[top_n_kabupaten:])
                 if not is_unknown_in_others :
                     top_kabupaten["Unknown"] = kabupaten_kota_count["Unknown"]
            kabupaten_to_plot = dict(sorted(top_kabupaten.items(), key=lambda item: item[1], reverse=True))
        else:
            kabupaten_to_plot = dict(sorted_kabupaten_items)

        fig2, ax2 = plt.subplots(figsize=(10, max(8, len(kabupaten_to_plot) * 0.5)))
        ax2.barh(list(kabupaten_to_plot.keys()), list(kabupaten_to_plot.values()), color='lightcoral')
        ax2.set_title(f'Distribusi berdasarkan Kabupaten/Kota', fontsize=20)
        ax2.set_xlabel('Jumlah', fontsize=16)
        ax2.set_ylabel('Kabupaten/Kota', fontsize=16)
        ax2.tick_params(axis='x', labelsize=14)
        ax2.tick_params(axis='y', labelsize=14)
        ax2.invert_yaxis()
        add_values_on_horizontal_bars(ax2, fontsize=12)
        plt.tight_layout()
        bar_kabupaten_img_buffer = BytesIO()
        plt.savefig(bar_kabupaten_img_buffer, format='png', bbox_inches='tight')
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
    return None, None, None # Fallback

# --- MODIFIED PDF Conversion Function ---
def convert_pdf_page_to_image_bytes(pdf_data_from_db, page_number=0, dpi=150, output_image_format="png"):
    """Converts a specific page of a PDF (from bytes or memoryview) to image bytes."""
    if not pdf_data_from_db:
        print("PDF CONVERSION: No PDF data provided.")
        return None

    actual_pdf_bytes = None
    if isinstance(pdf_data_from_db, memoryview):
        print(f"PDF CONVERSION: Input is memoryview (length {len(pdf_data_from_db)}), converting to bytes.")
        actual_pdf_bytes = pdf_data_from_db.tobytes()
    elif isinstance(pdf_data_from_db, bytes):
        print(f"PDF CONVERSION: Input is bytes (length {len(pdf_data_from_db)}).")
        actual_pdf_bytes = pdf_data_from_db
    else:
        print(f"PDF CONVERSION ERROR: Input data is type {type(pdf_data_from_db)}, expected 'bytes' or 'memoryview'. Cannot process.")
        try:
            data_repr = repr(pdf_data_from_db[:50]) if hasattr(pdf_data_from_db, '__getitem__') and len(pdf_data_from_db) >=50 else repr(pdf_data_from_db)
            print(f"PDF CONVERSION ERROR: Snippet: {data_repr}")
        except Exception as repr_e:
            print(f"PDF CONVERSION ERROR: Could not get snippet for type {type(pdf_data_from_db)}. Repr error: {repr_e}")
        return None

    if not actual_pdf_bytes:
        print("PDF CONVERSION ERROR: actual_pdf_bytes is None after type checks (should not happen if input was valid memoryview/bytes).")
        return None

    print(f"PDF CONVERSION: Attempting to open PDF stream of {len(actual_pdf_bytes)} bytes with PyMuPDF.")
    pdf_document = None
    try:
        # filetype="pdf" is important when opening from a stream
        pdf_document = fitz.open(stream=actual_pdf_bytes, filetype="pdf")

        if not len(pdf_document):
            print("PDF CONVERSION: PyMuPDF opened document, but it has no pages.")
            return None

        actual_page_number = max(0, min(page_number, len(pdf_document) - 1))
        page = pdf_document.load_page(actual_page_number)
        
        print(f"PDF CONVERSION: Loaded page {actual_page_number}. Attempting to get pixmap (DPI: {dpi}).")
        pixmap = page.get_pixmap(dpi=dpi)
        
        output_format_lower = output_image_format.lower()
        print(f"PDF CONVERSION: Pixmap obtained. Converting to bytes (format: {output_format_lower}).")
        image_bytes_result = pixmap.tobytes(output=output_format_lower)
        
        print(f"PDF CONVERSION: Successfully converted page {actual_page_number} to {output_image_format.upper()}. Output size: {len(image_bytes_result)} bytes.")
        return image_bytes_result

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        snippet = actual_pdf_bytes[:80] if actual_pdf_bytes else b'' # Show a slightly larger snippet
        print(f"PDF CONVERSION ERROR (PyMuPDF): {error_type}: {error_msg}.")
        print(f"PDF CONVERSION INFO: Input data length: {len(actual_pdf_bytes) if actual_pdf_bytes else 0}, Snippet (first 80 bytes): {snippet!r}")

        if "cannot open" in error_msg.lower() or \
           "format error" in error_msg.lower() or \
           "no objects found" in error_msg.lower() or \
           "cannot recognize stream type" in error_msg.lower() or \
           "mupdf error" in error_msg.lower(): # Common PyMuPDF error phrases
            print("PDF CONVERSION DETAIL: The error strongly suggests the input data is not a valid/recognized PDF for PyMuPDF, or it is corrupted.")
        elif "out of memory" in error_msg.lower():
            print("PDF CONVERSION DETAIL: PyMuPDF ran out of memory. PDF might be too complex or DPI too high for available resources.")
        
        # --- Optional: Save problematic PDF data for manual inspection ---
        # import time
        # timestamp = time.strftime("%Y%m%d-%H%M%S")
        # error_filename = f"debug_pdf_failed_{timestamp}.pdf"
        # try:
        #     with open(error_filename, "wb") as f_err:
        #         f_err.write(actual_pdf_bytes)
        #     print(f"PDF CONVERSION DEBUG: Problematic PDF data (if it was PDF) saved to '{error_filename}' for inspection.")
        # except Exception as save_e:
        #     print(f"PDF CONVERSION DEBUG: Could not save problematic data: {save_e}")
        # --- End Optional Save ---
        return None
    finally:
        if pdf_document:
            print("PDF CONVERSION: Closing PyMuPDF document.")
            pdf_document.close()

# --- MODIFIED Image Preparation Function ---
def prepare_image_for_frontend(original_data_from_db, target_size=(350, 200), final_output_format='PNG'):
    """
    If original_data_from_db is a PDF, converts its first page to an image.
    Then, resizes the (converted or original) image, and encodes to base64.
    """
    if not original_data_from_db:
        print("PREPARE IMAGE: original_data_from_db is None or empty.")
        return None

    print(f"PREPARE IMAGE: Received data of type {type(original_data_from_db)}, length {len(original_data_from_db) if hasattr(original_data_from_db, '__len__') else 'N/A'}. Target output format: {final_output_format}.")
    
    image_bytes_to_process = None

    # Attempt PDF conversion first
    # convert_pdf_page_to_image_bytes handles memoryview to bytes conversion internally
    converted_from_pdf_bytes = convert_pdf_page_to_image_bytes(
        original_data_from_db, 
        page_number=0, 
        dpi=200, # Higher DPI for initial render, then thumbnail
        output_image_format="png" # PyMuPDF will output PNG bytes
    )

    if converted_from_pdf_bytes:
        image_bytes_to_process = converted_from_pdf_bytes
        print(f"PREPARE IMAGE: Using PDF-converted image data (now PNG, {len(image_bytes_to_process)} bytes).")
    else:
        print("PREPARE IMAGE: PDF conversion failed or data was not a processable PDF. Attempting to process original data with Pillow.")
        # Ensure original_data_from_db is bytes for Pillow if it wasn't a PDF (or PDF conversion failed)
        if isinstance(original_data_from_db, memoryview):
            print("PREPARE IMAGE: Original data was memoryview, converting to bytes for Pillow.")
            image_bytes_to_process = original_data_from_db.tobytes()
        elif isinstance(original_data_from_db, bytes):
            print("PREPARE IMAGE: Original data was already bytes for Pillow.")
            image_bytes_to_process = original_data_from_db
        else:
            # This case should ideally be caught by convert_pdf_page_to_image_bytes if it was an unsupported type
            print(f"PREPARE IMAGE ERROR: Original data for Pillow is neither bytes nor memoryview (type: {type(original_data_from_db)}). Cannot process with Pillow.")
            return None

    if not image_bytes_to_process:
        print("PREPARE IMAGE ERROR: No image bytes to process after PDF check and original data check.")
        return None

    try:
        img_io = io.BytesIO(image_bytes_to_process)
        img = Image.open(img_io) # Pillow opens the (PNG from PDF, or original JFIF/PNG/etc.)

        original_pil_format = img.format
        print(f"PREPARE IMAGE: Pillow opened image. Original format (Pillow's view): {original_pil_format}, Mode: {img.mode}, Size: {img.size}")

        if final_output_format.upper() == 'JPEG' and img.mode not in ('RGB', 'L'):
            print(f"PREPARE IMAGE: Converting image mode from {img.mode} to RGB for JPEG saving.")
            img = img.convert('RGB')
        elif final_output_format.upper() == 'PNG' and img.mode == 'CMYK':
            print(f"PREPARE IMAGE: Converting image mode from CMYK to RGBA for PNG saving.")
            img = img.convert('RGBA')
        elif img.mode == 'P': # Palette mode
             # Convert P mode to RGBA if it has transparency, otherwise RGB, for broader compatibility
            if 'transparency' in img.info:
                print(f"PREPARE IMAGE: Converting image mode from {img.mode} (with transparency) to RGBA.")
                img = img.convert('RGBA')
            else:
                print(f"PREPARE IMAGE: Converting image mode from {img.mode} to RGB.")
                img = img.convert('RGB')


        resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
        img.thumbnail(target_size, resample_filter)
        print(f"PREPARE IMAGE: Resized to fit within {target_size}. New size: {img.size}")

        output_io = io.BytesIO()
        save_params = {}
        if final_output_format.upper() == 'JPEG':
            save_params['quality'] = 85
        # For PNG, 'optimize=True' can reduce file size but takes longer
        # elif final_output_format.upper() == 'PNG':
        #     save_params['optimize'] = True 
            
        img.save(output_io, format=final_output_format.upper(), **save_params)

        encoded_image_string = base64.b64encode(output_io.getvalue()).decode('utf-8')
        print(f"PREPARE IMAGE: Successfully processed and encoded image to base64 ({final_output_format}). Output string length: {len(encoded_image_string)}")
        return encoded_image_string
        
    except UnidentifiedImageError as un_err:
        print(f"PREPARE IMAGE ERROR (Pillow): UnidentifiedImageError: {un_err}. "
              "Pillow couldn't recognize the image format. This occurs if PDF conversion failed AND "
              "the original data was not a Pillow-compatible image (e.g., corrupted, or a PDF PyMuPDF couldn't handle).")
        snippet = image_bytes_to_process[:80] if image_bytes_to_process else b''
        print(f"PREPARE IMAGE ERROR (Pillow): Data snippet (first 80 bytes): {snippet!r}")
        return None
    except Exception as e:
        print(f"PREPARE IMAGE ERROR (Pillow): Error during Pillow processing (resizing/encoding): {type(e).__name__}: {e}")
        return None

@app.route('/qc-process')
def qc_process():
    # ... (qc_process code remains largely the same, calls prepare_image_for_frontend) ...
    # Ensure it correctly passes the raw data from DB (ktp_result[0], etc.)
    # to prepare_image_for_frontend.
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
            output_image_type = 'PNG'

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
                    # ktp_result[0] is the raw data from DB (likely memoryview or bytes)
                    ktp_image_url = prepare_image_for_frontend(ktp_result[0], ktp_npwp_preview_size, final_output_format=output_image_type)
                    if not ktp_image_url: print("QC PROCESS: KTP image preparation failed.")
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
                    if not npwp_image_url: print("QC PROCESS: NPWP image preparation failed.")
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
                    if not form_data3_image_url: print("QC PROCESS: Form_data3 image preparation failed.")
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
            error_message = f"An unexpected error occurred: {type(e).__name__}: {e}"
            print(f"QC PROCESS UNEXPECTED ERROR: {type(e).__name__}: {e}")
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
    # ... (index route remains largely the same) ...
    conn = connect_to_db()
    cursor = None
    if not conn:
        return "Database connection failed for index page."

    total_register, total_unique_provinces, total_unique_kabupaten = 0, 0, 0
    user_data, data_table_rows = [], []
    pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url = None, None, None
    search_query = request.args.get('search', '').strip()
    colnames = []

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
        
        if cursor.description:
            colnames = [desc[0] for desc in cursor.description]
            data_table_rows = [dict(zip(colnames, row)) for row in data_table_rows_raw]
        else:
            data_table_rows = []

        pie_chart_url, bar_provinsi_chart_url, bar_kabupaten_chart_url = generate_charts()

    except psycopg2.Error as e:
        print(f"INDEX PAGE DB ERROR: {e}")
        return f"PostgreSQL Error on Index Page: {e}"
    except Exception as e:
        print(f"INDEX PAGE ERROR: {type(e).__name__}: {e}")
        return f"Error fetching data for Index Page: {type(e).__name__}: {e}"
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
        data_table_header=colnames,
        data_table_rows=data_table_rows,
        user_data=user_data,
    )
    return "Error in index." # Fallback

# --- MODIFIED Direct Image Route ---
@app.route('/image_direct/<doc_type>/<nomor_input_str>')
def get_image_direct(doc_type, nomor_input_str):
    conn = connect_to_db()
    cursor = None
    if not conn:
        return "Database connection failed", 503

    try:
        cursor = conn.cursor()
        table_map = {'ktp': 'ktp_data2', 'npwp': 'npwp_data2', 'form': 'form_data3'}
        table_name = table_map.get(doc_type.lower())
        if not table_name:
            return "Invalid document type", 400

        cursor.execute(f"SELECT scanned_image FROM {table_name} WHERE nomor_input = %s LIMIT 1", (nomor_input_str,))
        db_row = cursor.fetchone()

        if db_row and db_row[0]:
            original_data_from_db = db_row[0] # This is likely memoryview or bytes
            image_to_serve_bytes = None
            mimetype = 'image/png'  # Default, as PDF or other conversions will target PNG

            print(f"DIRECT IMAGE: Fetched data of type {type(original_data_from_db)}, length {len(original_data_from_db) if hasattr(original_data_from_db, '__len__') else 'N/A'} for {doc_type}/{nomor_input_str}.")

            # 1. Attempt PDF conversion
            # convert_pdf_page_to_image_bytes handles memoryview internally
            converted_pdf_bytes = convert_pdf_page_to_image_bytes(
                original_data_from_db, 
                output_image_format="png", 
                dpi=150 # DPI for direct viewing
            )

            if converted_pdf_bytes:
                image_to_serve_bytes = converted_pdf_bytes
                mimetype = 'image/png'
                print(f"DIRECT IMAGE: Serving PDF ({doc_type}/{nomor_input_str}) converted to PNG ({len(image_to_serve_bytes)} bytes).")
            else:
                # 2. PDF conversion failed or it wasn't a PDF. Try to process with Pillow.
                print(f"DIRECT IMAGE: PDF conversion failed or not a PDF for {doc_type}/{nomor_input_str}. Attempting to process original data with Pillow.")
                
                bytes_for_pillow = None
                if isinstance(original_data_from_db, memoryview):
                    print("DIRECT IMAGE: Original data was memoryview, converting to bytes for Pillow.")
                    bytes_for_pillow = original_data_from_db.tobytes()
                elif isinstance(original_data_from_db, bytes):
                    print("DIRECT IMAGE: Original data was already bytes for Pillow.")
                    bytes_for_pillow = original_data_from_db
                
                if not bytes_for_pillow:
                    print(f"DIRECT IMAGE ERROR: Original data for Pillow is not bytes/memoryview (type: {type(original_data_from_db)}). Cannot process.")
                    return "Error: Invalid data type from database for non-PDF image processing.", 500

                try:
                    img_io = io.BytesIO(bytes_for_pillow)
                    img = Image.open(img_io)
                    img_format_upper = img.format.upper() if img.format else "UNKNOWN"
                    
                    print(f"DIRECT IMAGE (Pillow): Opened image. Original format (Pillow's view): {img_format_upper}, Mode: {img.mode}, Size: {img.size}")

                    if img_format_upper in ["JPEG", "PNG", "GIF", "WEBP"]:
                        image_to_serve_bytes = bytes_for_pillow # Serve original bytes
                        mimetype = Image.MIME.get(img_format_upper) or f'image/{img_format_upper.lower()}'
                        print(f"DIRECT IMAGE: Serving original {img_format_upper} image.")
                    else:
                        print(f"DIRECT IMAGE: Original format {img_format_upper} not a standard web format or unknown. Converting to PNG.")
                        output_io = io.BytesIO()
                        # Handle potential mode issues before saving as PNG
                        if img.mode == 'P' and 'transparency' in img.info: img = img.convert("RGBA")
                        elif img.mode == 'CMYK': img = img.convert("RGB") # PNGs are better off as RGB/RGBA
                        elif img.mode == 'P': img = img.convert("RGB") # Convert P without transparency to RGB
                        
                        img.save(output_io, format="PNG")
                        image_to_serve_bytes = output_io.getvalue()
                        mimetype = 'image/png'
                        print(f"DIRECT IMAGE: Converted to PNG ({len(image_to_serve_bytes)} bytes).")
                        
                except UnidentifiedImageError:
                    print(f"DIRECT IMAGE ERROR (Pillow): Pillow UnidentifiedImageError for {doc_type}/{nomor_input_str}. Cannot serve as image.")
                    snippet = bytes_for_pillow[:80] if bytes_for_pillow else b''
                    print(f"DIRECT IMAGE ERROR (Pillow): Data snippet (first 80 bytes): {snippet!r}")
                    return "Error: Document is not a recognized image format (by Pillow) or is corrupted.", 415 # Unsupported Media Type
                except Exception as e_img:
                    print(f"DIRECT IMAGE ERROR (Pillow): Error processing non-PDF image {doc_type}/{nomor_input_str} with Pillow: {type(e_img).__name__}: {e_img}")
                    return "Error processing image with Pillow.", 500

            if image_to_serve_bytes:
                return Response(image_to_serve_bytes, mimetype=mimetype)
            else:
                print(f"DIRECT IMAGE ERROR: image_to_serve_bytes is None for {doc_type}/{nomor_input_str} after all processing attempts. This is unexpected.")
                return "Error: Unable to prepare image for display.", 500
        else:
            return "Document not found or no image data in database", 404
    except Exception as e:
        print(f"DIRECT IMAGE ROUTE UNEXPECTED ERROR for {doc_type}/{nomor_input_str}: {type(e).__name__}: {e}")
        return "Error fetching/processing document from database", 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


if __name__ == '__main__':
    static_folder = os.path.join(app.root_path, 'static')
    magnifying_glass_path = os.path.join(static_folder, 'magnifying-glass.png')
    if not os.path.exists(magnifying_glass_path):
        print(f"WARNING: Magnifying glass image not found at {magnifying_glass_path}. Zoom feature might not show icon.")

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)