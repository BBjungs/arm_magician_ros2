"""One-sheet, physical-size calibration printout (no robot operations)."""

import hashlib
import html
import json
import xml.etree.ElementTree as ET


def calibration_print_page(svg_bytes, mode):
    """Embed the exact API SVG; never resize the marker artwork to fit paper."""
    svg = svg_bytes.decode('utf-8')
    root = ET.fromstring(svg)
    board = json.loads(root.find('{http://www.w3.org/2000/svg}metadata').text)
    width = float(root.attrib['width'].removesuffix('mm'))
    height = float(root.attrib['height'].removesuffix('mm'))
    if width > 190 or height > 230:
        raise ValueError('Board exceeds this A4 template; use the SVG at actual size on larger paper')
    revision = hashlib.sha256(svg_bytes).hexdigest()[:12]
    centers = [board['markers'][str(i)]['center_mm'] for i in board['required_ids']]
    span_x = max(p[0] for p in centers) - min(p[0] for p in centers)
    span_y = max(p[1] for p in centers) - min(p[1] for p in centers)
    pose = html.escape(json.dumps(board['pose_base'], ensure_ascii=False))
    dictionary = html.escape(board['dictionary'])
    return f'''<!doctype html>
<html lang="th"><head><meta charset="utf-8">
<title>Dobot Calibration — A4 / 100%</title>
<style>
@page {{ size: A4 portrait; margin: 10mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: #111; background: #eee; font-family: sans-serif; }}
.controls {{ max-width: 900px; margin: 20px auto; padding: 20px; background: white; }}
.controls li {{ margin: 10px 0; }}
button, a {{ padding: 8px; }}
.sheet {{ width: 190mm; margin: 15px auto; background: white; text-align: center; }}
.artwork {{ width: {width:g}mm; height: {height:g}mm; margin: 0 auto; }}
.artwork svg {{ display: block; width: {width:g}mm; height: {height:g}mm; max-width: none; }}
.caption {{ font-size: 9pt; line-height: 1.35; padding: 2mm 0; overflow-wrap: anywhere; }}
.pose {{ font-family: monospace; font-size: 8pt; }}
@media print {{
 body {{ background: white; }}
 .controls {{ display: none !important; }}
 .sheet {{ margin: 0; break-inside: avoid; }}
}}
</style></head><body>
<section class="controls">
<h1>แผ่น Calibration สำหรับ Dobot</h1>
<p>โหมด: {html.escape(mode)} — แผ่นนี้ใช้หาตำแหน่งกล้องกับแขน
โดยอ้างอิงแผ่นที่วัดตำแหน่งในฐานหุ่นยนต์แล้ว ไม่ใช่แผ่นหา intrinsics ของเลนส์</p>
<button id="printBoard" type="button">พิมพ์ / บันทึก PDF</button>
<a href="/api/vision/calibration/board.svg?mode={html.escape(mode)}" download="dobot-calibration.svg">ดาวน์โหลด SVG ต้นฉบับ</a>
<ol>
<li>เลือก A4 แนวตั้ง, Scale 100% / Actual size, ปิด Fit to page และหัว/ท้ายกระดาษ
ตรวจตัวอย่างก่อนพิมพ์ว่ามีหนึ่งหน้า ห้าม Mirror หรือปรับขนาดภาพ</li>
<li>วัดขอบดำ Marker ให้ได้ {board['marker_length_mm']:g} มม. ทั้งสองแกน
และวัดระยะศูนย์กลางแนวนอน {span_x:g} / แนวตั้ง {span_y:g} มม.
หากขนาดไม่ตรงให้แก้การตั้งค่าพิมพ์ก่อนใช้งาน</li>
<li>ติดแผ่นบนพื้นแข็ง เรียบ ด้าน ไม่บิดงอ เว้นบริเวณขาวรอบ Marker
จุดกากบาทคือกำเนิดแผ่น +X ไปขวา, +Y ขึ้น, +Z ออกจากหน้ากระดาษ</li>
<li>วัดตำแหน่งกำเนิดและมุมแผ่นเทียบฐาน Dobot ให้ตรง pose_base ด้านล่าง
รวมความหนาแผ่นด้วย ค่านี้เป็นค่าตั้งต้นในระบบ ไม่ใช่ผลวัดอัตโนมัติ
ถ้าไม่ตรง ต้องแก้ config/aruco_board.yaml ที่ระบบใช้อยู่ก่อนคาลิเบรต</li>
<li>สำหรับกล้องปลายแขน เลือก Eye-in-hand ยืนยันว่าขายึดกล้องสัมพันธ์กับ TCP
ตามโมเดลและไม่คลอน ให้แขนหยุดและเห็น Marker ครบทุกตัว แล้วใช้ปุ่มคาลิเบรตในเว็บ</li>
<li>หลังผ่าน ให้ตรวจจุดอ้างอิงที่วัดจริงหลายจุดก่อนทดสอบ Dry Run
การผ่าน Calibration ไม่ได้อนุญาตให้หยิบจริง และต้องวัดระดับหยิบแยกต่างหาก</li>
</ol></section>
<main class="sheet">
<div class="artwork">{svg}</div>
<div class="caption">DOBOT BOARD v2 · {dictionary} · print ID {revision}<br>
Marker: {board['marker_length_mm']:g} mm · center span: {span_x:g} × {span_y:g} mm
· artwork: {width:g} × {height:g} mm<br>
Configured fixture pose — MUST measure before calibration (mm / deg):
<div class="pose">{pose}</div>
Scale checked: __________  Fixture measured: __________  Date: __________</div>
</main><script src="/static/calibration_print.js"></script></body></html>'''
