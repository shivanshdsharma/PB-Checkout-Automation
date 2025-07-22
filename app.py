import streamlit as st
import pandas as pd
from PIL import Image
import google.generativeai as genai
import json
import re
import io

# ---- CONFIG ----
MODEL_NAME = "models/gemini-2.5-flash"
MENU_FILE = "menu.xlsx"

#Load API KEY
load_dotenv()
API_KEY = os.getenv("API_KEY")
genai.configure(api_key=API_KEY)

# ---- Gemini Setup ----
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name=MODEL_NAME)

# ---- Menu (read 'Name' column only) ----
menu_df = pd.read_excel(MENU_FILE)
menu_df = menu_df.dropna(subset=["Name"])
product_names = menu_df["Name"].tolist()

# ---- Extract JSON utility ----
def extract_json(text):
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}
    try:
        return json.loads(text)
    except Exception:
        return {}

# ---- UI Layout ----
st.set_page_config(page_title="Paris Baguette Checkout Automation", layout="wide")
main_col, side_col = st.columns([3, 1], gap="large")

with main_col:
    st.markdown("<h2 style='text-align:center;'>Paris Baguette Checkout</h2>", unsafe_allow_html=True)
    cam_img = st.camera_input("Take Tray Photo")
    upload_img = st.file_uploader("Or upload tray image", type=["jpg", "jpeg", "png"])
    photo = cam_img if cam_img else upload_img
    checkout = st.button("Checkout", use_container_width=True)

with side_col:
    result_placeholder = st.empty()

if photo and checkout:
    with st.spinner("Detecting items..."):
        image_pil = Image.open(photo).convert("RGB")
        # Resize for efficiency
        if image_pil.width > 1024:
            ratio = 1024.0 / image_pil.width
            image_pil = image_pil.resize((1024, int(image_pil.height * ratio)), Image.LANCZOS)

        menu_list = ", ".join(product_names[:10]) + (", ..." if len(product_names) > 10 else "")
        prompt = (
            f"You are a checkout assistant for Paris Baguette. Given ONLY this menu: {menu_list}, "
            "detect and count all items in the tray photo. "
            'Return ONLY a JSON object: {"Item1": quantity, "Item2": quantity}. No additional text.'
        )

        try:
            response = model.generate_content(
                [prompt, image_pil],
                generation_config={"temperature": 0.1, "max_output_tokens": 1024},
                stream=False,
            )
        except Exception as e:
            result_placeholder.error(f"Gemini API error: {e}")
            st.stop()

        # Validate Gemini's response
        if not hasattr(response, "candidates") or not response.candidates:
            result_placeholder.error("No response candidates from Gemini. Try another image or check quota/content policy.")
            st.stop()
        candidate = response.candidates[0]
        if not hasattr(candidate, "content") or not getattr(candidate.content, "parts", []):
            code = getattr(candidate, "finish_reason", "UNKNOWN")
            result_placeholder.error(f"Gemini returned no output (finish_reason={code}).")
            st.stop()

        try:
            answer = response.text
        except Exception as e:
            result_placeholder.error(f"Gemini output parsing failed: {e}")
            st.stop()

        detected_items = extract_json(answer)
        if not detected_items:
            result_placeholder.error("No parsable output from Gemini. Raw output:\n" + str(answer))
            st.stop()

        # ---- Output in Left Pane ----
        with result_placeholder.container():
            st.markdown("<h4>Detected Tray Items</h4>", unsafe_allow_html=True)
            for item, qty in detected_items.items():
                st.write(f"{item} × {qty}")
            if not detected_items:
                st.info("No items detected in tray.")
            st.image(image_pil, caption="Tray Photo", width=320)
            with st.expander("Show Gemini Raw Output"):
                st.code(answer)

elif not photo:
    result_placeholder.info("Capture or upload a tray image to begin. Only detected item names will populate here after checkout.")
