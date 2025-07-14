import streamlit as st
import json
import io
import re
from PIL import Image
from fuzzywuzzy import process
import google.generativeai as genai
from dotenv import load_dotenv

# ——— CONFIG ———
TITLE         = "🥐 Paris Baguette Checkout Automation"
MENU_FILE     = "menu.json"
API_KEY_FILE  = "api_key.txt"
FUZZY_THRESH  = 70

# ——— LOAD API KEY ———
load_dotenv()
API_KEY = os.getenv("API_KEY")
genai.configure(api_key=API_KEY)

# ——— LOAD MENU ———
raw_menu = json.load(open(MENU_FILE))
MENU_DISPLAY = raw_menu
MENU = {k: float(v.replace("$", "")) for k, v in raw_menu.items()}
MENU_ITEMS = list(MENU.keys())

# ——— GEMINI IMAGE DETECTION ———
def detect_with_menu(image_bytes):
    menu_list = "\n".join(f"- {item}" for item in MENU_ITEMS)
    prompt = (
        "You're given a bakery tray image. Here's the Paris Baguette menu:\n"
        f"{menu_list}\n\n"
        "Which of these items are visible and how many of each?\n"
        "Respond in the format:\n* Item Name (xN)\nOnly list menu items."
    )
    model = genai.GenerativeModel("gemini-1.5-flash")
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    response = model.generate_content([prompt, img])
    return response.text.strip()

# ——— PARSE RESPONSE ———
ITEM_RE = re.compile(r"^[\*\-\•]\s*(.+?)\s*\([x×](\d+)\)", re.MULTILINE)
def parse(caption):
    return ITEM_RE.findall(caption)

# ——— BILL GENERATION ———
def build_bill(parsed):
    bill = {}
    total = 0.0
    for name, count_str in parsed:
        count = int(count_str)
        match, score = process.extractOne(name, MENU_ITEMS)
        if score >= FUZZY_THRESH:
            price = MENU[match]
            subtotal = price * count
            bill[match] = bill.get(match, {"qty": 0, "subtotal": 0.0})
            bill[match]["qty"] += count
            bill[match]["subtotal"] += subtotal
            total += subtotal
    return bill, total

# ——— STREAMLIT UI ———
st.set_page_config(page_title=TITLE, layout="wide")
st.title(TITLE)

col1, col2 = st.columns([5, 1])
with col1:
    uploaded = st.file_uploader("📤 Upload Tray Image", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
with col2:
    st.markdown(" ")
    run = st.button("🧾 Checkout", use_container_width=True)

if uploaded:
    img = Image.open(uploaded).convert("RGB")
    st.image(img, caption="Your Tray", width=300)  # 👈 Smaller image display

    if run:
        st.info("🧠 Detecting items with Gemini… please wait ⏳")
        image_bytes = uploaded.getvalue()

        try:
            caption = detect_with_menu(image_bytes)
        except Exception as e:
            st.error(f"❌ Gemini API Error: {e}")
            st.stop()

        st.subheader("🧠 Gemini Output")
        st.text(caption)

        parsed = parse(caption)
        if not parsed:
            st.warning("⚠️ No valid items detected. Try another image.")
            st.stop()

        st.subheader("📖 Parsed Items")
        for name, count in parsed:
            st.write(f"• {name} × {count}")

        bill, total = build_bill(parsed)
        if not bill:
            st.error("❌ No matching items found in `menu.json`.")
            st.stop()

        st.sidebar.title("🧾 Final Bill")
        for item, data in bill.items():
            st.sidebar.write(f"{item} × {data['qty']} = ${data['subtotal']:.2f}")
        st.sidebar.markdown("---")
        st.sidebar.write(f"**Total: ${total:.2f}**")

else:
    st.info("Upload a tray image to begin.")
