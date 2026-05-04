import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ページ設定
st.set_page_config(page_title="PC Build Simulator", layout="wide")

# タイトル
st.title("🖥️ PC Build Simulator")
st.markdown("---")

# CSVをロード
@st.cache_data
def load_parts_data():
    return pd.read_csv("parts.csv")

parts_df = load_parts_data()

# パーツタイプごとに分類
cpu_parts = parts_df[parts_df["type"] == "CPU"][["name", "price"]].reset_index(drop=True)
gpu_parts = parts_df[parts_df["type"] == "GPU"][["name", "price"]].reset_index(drop=True)
mem_parts = parts_df[parts_df["type"] == "MEM"][["name", "price"]].reset_index(drop=True)
ssd_parts = parts_df[parts_df["type"] == "SSD"][["name", "price"]].reset_index(drop=True)

# サイドバーでパーツ選択
st.sidebar.header("🔧 パーツを選択")

selected_cpu = st.sidebar.selectbox("CPU", ["選択なし"] + cpu_parts["name"].tolist())
selected_gpu = st.sidebar.selectbox("GPU", ["選択なし"] + gpu_parts["name"].tolist())
selected_mem = st.sidebar.selectbox("メモリ", ["選択なし"] + mem_parts["name"].tolist())
selected_ssd = st.sidebar.selectbox("ストレージ", ["選択なし"] + ssd_parts["name"].tolist())

# 選択したパーツの価格を取得する関数
def get_price(parts_list, part_name):
    if part_name == "選択なし":
        return 0
    result = parts_list[parts_list["name"] == part_name]["price"]
    return result.values[0] if len(result) > 0 else 0

# 価格を計算
cpu_price = get_price(cpu_parts, selected_cpu)
gpu_price = get_price(gpu_parts, selected_gpu)
mem_price = get_price(mem_parts, selected_mem)
ssd_price = get_price(ssd_parts, selected_ssd)
total_price = cpu_price + gpu_price + mem_price + ssd_price

# メイン画面：構成一覧
st.header("📋 PC構成一覧")

# 構成表を作成
config_data = {
    "パーツ": ["CPU", "GPU", "メモリ", "ストレージ", "合計"],
    "商品名": [
        selected_cpu if selected_cpu != "選択なし" else "-",
        selected_gpu if selected_gpu != "選択なし" else "-",
        selected_mem if selected_mem != "選択なし" else "-",
        selected_ssd if selected_ssd != "選択なし" else "-",
        ""
    ],
    "価格": [
        f"¥{cpu_price:,.0f}" if cpu_price > 0 else "¥0",
        f"¥{gpu_price:,.0f}" if gpu_price > 0 else "¥0",
        f"¥{mem_price:,.0f}" if mem_price > 0 else "¥0",
        f"¥{ssd_price:,.0f}" if ssd_price > 0 else "¥0",
        f"¥{total_price:,.0f}"
    ]
}

config_df = pd.DataFrame(config_data)
st.dataframe(config_df, width='stretch', hide_index=True)

# 合計金額を強調表示
st.metric("💰 合計金額", f"¥{total_price:,.0f}")

# コメント生成ロジック
def generate_comment(cpu_score, gpu_score, mem_price, total):
    comments = []
    
    # GPU性能に基づくコメント
    if gpu_score >= 90:
        comments.append("🎮 ハイエンド・ゲーミング向け！重いゲームも快適に動作します。")
    elif gpu_score >= 75:
        comments.append("🎮 ゲーミング向け。最新ゲームも中程度以上の設定で楽しめます。")
    elif gpu_score >= 60:
        comments.append("🎮 軽～中程度のゲーミング向け。スポーツゲームなどに最適。")
    elif gpu_score > 0:
        comments.append("💻 軽めのゲーム・動画視聴に適しています。")
    
    # CPU性能に基づくコメント
    if cpu_score >= 85:
        comments.append("⚡ 最高スペックのCPU。マルチタスク・クリエイティブ作業に最適。")
    elif cpu_score >= 75:
        comments.append("⚡ 高性能CPU。快適にマルチタスク処理できます。")
    elif cpu_score >= 68:
        comments.append("💪 バランスの取れたCPU。日常利用は十分快適。")
    
    # 価格に基づくコメント
    if total <= 100000:
        comments.append("💡 コスパ重視の構成。予算を抑えたい方向け。")
    elif total <= 200000:
        comments.append("💡 バランス型の構成。一般的なニーズに対応。")
    else:
        comments.append("💎 高級構成。最高のパフォーマンスを求める方向け。")
    
    # 完全性のコメント
    selected_count = sum([selected_cpu != "選択なし", selected_gpu != "選択なし", 
                         selected_mem != "選択なし", selected_ssd != "選択なし"])
    if selected_count == 4:
        comments.append("✅ すべてのパーツが選択されています。")
    elif selected_count > 0:
        comments.append(f"⚠️ まだ{4 - selected_count}個のパーツが未選択です。")
    else:
        comments.append("⚠️ パーツをまず選択してください。")
    
    return "\n".join(comments)

# パーツのスコア取得
cpu_score = 0
gpu_score = 0
if selected_cpu != "選択なし":
    cpu_score = parts_df[(parts_df["type"] == "CPU") & (parts_df["name"] == selected_cpu)]["score"].values[0]
if selected_gpu != "選択なし":
    gpu_score = parts_df[(parts_df["type"] == "GPU") & (parts_df["name"] == selected_gpu)]["score"].values[0]

# コメント表示
st.header("💬 構成コメント")
st.info(generate_comment(cpu_score, gpu_score, mem_price, total_price))

# PDF出力機能
def generate_pdf(config_data, total_price, comment):
    """PDF見積書を生成"""
    buffer = BytesIO()
    
    # SimpleDocTemplateを使用
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           rightMargin=15*mm, leftMargin=15*mm,
                           topMargin=15*mm, bottomMargin=15*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # タイトル
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("PC 見積書", title_style))
    elements.append(Spacer(1, 10))
    
    # 日付
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT
    )
    elements.append(Paragraph(f"発行日: {datetime.now().strftime('%Y年%m月%d日')}", date_style))
    elements.append(Spacer(1, 15))
    
    # 構成表
    table_data = [
        ["パーツ", "商品名", "価格"]
    ]
    for i in range(4):
        table_data.append([
            config_data["パーツ"][i],
            config_data["商品名"][i],
            config_data["価格"][i]
        ])
    table_data.append(["", "合計", f"¥{total_price:,.0f}"])
    
    table = Table(table_data, colWidths=[40*mm, 100*mm, 50*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e6f2ff')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f9f9f9')])
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # コメント
    comment_style = ParagraphStyle(
        'CommentStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#555555'),
        spaceAfter=6
    )
    elements.append(Paragraph("<b>構成コメント:</b>", styles['Heading3']))
    for line in comment.split('\n'):
        elements.append(Paragraph(f"• {line}", comment_style))
    
    # PDF生成
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ダウンロードボタン
st.header("📥 ダウンロード")
if total_price > 0:
    comment = generate_comment(cpu_score, gpu_score, mem_price, total_price)
    pdf_buffer = generate_pdf(config_data, total_price, comment)
    
    st.download_button(
        label="📄 PDF見積書をダウンロード",
        data=pdf_buffer,
        file_name=f"PC見積書_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf"
    )
else:
    st.warning("⚠️ 最低1つ以上のパーツを選択してください。")

st.markdown("---")
st.markdown("**PC Build Simulator** © 2026 | 初心者向けPC構成シミュレータ")
