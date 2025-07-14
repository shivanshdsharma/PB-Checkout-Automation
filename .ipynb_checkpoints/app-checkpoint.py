import streamlit as st
import json
import io
from PIL import Image
from fuzzywuzzy import process
import replicate

# ——— CONFIG ———
TITLE = "🥐 Paris Baguette Checkout Automation (Replicate)"
MENU_FILE = "menu.json"
REPLICATE_API_KEY = "api_key.txt"
FUZZY_THRESH = 70
MODEL_VERSION = "salesforce/blip:db21e45b12e9814e71db6601e0a1c63f129c6c4079a223f77e2aa2e0d011a5de"

# ——— LOAD MENU ———
raw_menu = json.load(open(MENU_FILE))
MENU_DISPLAY = raw_menu
MENU = {k: float(v.replace("$", "")) for k, v in raw_menu.items()}
MENU_ITEMS = list(MENU.keys())

# ——— CAPTIONING VIA REPLICATE ———
def detect_with_replicate(image_bytes):
    client = replicate.Client(api_token=REPLICATE_API_KEY)
    img_io = io.BytesIO(image_bytes)
    output = client.run(MODEL_VERSION, input={"image": img_io})
    return output  # returns caption string

# ——— FUZZY MATCH ITEMS ———
def extract_menu_items(caption):
    matched = []
    for item in MENU_ITEMS:
        score = process.extractOne(item.lower(), [caption.lower()])
        if score and score[1] >= FUZZY_THRESH:
            matched.append(item)
    return matched

# ——— BUILD BILL ———
def build_bill(matched_items):
    bill = {}
    total = 0.0
    for item in matched_items:
        price = MENU[item]
        bill[item] = bill.get(item, {"qty": 0, "subtotal": 0.0})
        bill[item]["qty"] += 1
        bill[item]["subtotal"] += price
        total += price
    return bill, total

# ——— STREAMLIT UI ———
st.set_page_config(page_title=TITLE, layout="wide")
st.title(TITLE)

col1, col2 = st.columns([5, 1])
with col1:
    uploaded = st.file_uploader("📤 Upload Tray Image", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
with col2:
    st.markdown(" ")
    run = st.button("🧾 Checkout", use_container_width=True)

if uploaded:
    img = Image.open(uploaded).convert("RGB")
    st.image(img, caption="Your Tray", width=400)

    if run:
        st.info("🧠 Detecting items… please wait ⏳")
        try:
            image_bytes = uploaded.getvalue()
            caption = detect_with_replicate(image_bytes)
        except Exception as e:
            st.error(f"❌ Replicate error: {e}")
            st.stop()

        st.subheader("🧠 Caption Generated")
        st.text(caption)

        matched_items = extract_menu_items(caption)

        if not matched_items:
            st.warning("⚠️ No matching menu items found. Try another image.")
            st.stop()

        st.subheader("📖 Matched Items")
        for item in matched_items:
            st.write(f"• {item}")

        bill, total = build_bill(matched_items)

        if not bill:
            st.error("❌ No valid items found in menu.json.")
            st.stop()

        st.sidebar.title("🧾 Final Bill")
        for item, data in bill.items():
            st.sidebar.write(f"{item} × {data['qty']} = ${data['subtotal']:.2f}")
        st.sidebar.markdown("---")
        st.sidebar.write(f"**Total: ${total:.2f}**")

else:
    st.info("Please upload a tray image to begin.")
