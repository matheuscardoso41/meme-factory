import streamlit as st
import json
import io
import zipfile
import re
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai

# Configuração da Página
st.set_page_config(
    page_title="Meme Factory AI",
    page_icon="🎭",
    layout="wide"
)

st.title("🎭 Meme Factory AI")
st.markdown("Gere memes incríveis usando Inteligência Artificial!")

# Inicialização de Estado
if "meme_phrases" not in st.session_state:
    st.session_state.meme_phrases = []
if "original_image" not in st.session_state:
    st.session_state.original_image = None
if "selected_phrases" not in st.session_state:
    st.session_state.selected_phrases = {}
if "iteration_count" not in st.session_state:
    st.session_state.iteration_count = 0

# --- Funções Utilitárias de Imagem ---

def resize_image(image: Image.Image, max_width: int = 800) -> Image.Image:
    if image.width > max_width:
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        return image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    return image.copy()

def get_font(size: int) -> ImageFont.FreeTypeFont:
    font_paths = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arial.ttf"
    ]
    
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    
    return ImageFont.load_default()

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
        except AttributeError:
             text_width = draw.textlength(test_line, font=font)

        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines

def draw_text_with_outline(draw: ImageDraw.ImageDraw, position: tuple, text: str, 
                           font: ImageFont.FreeTypeFont, fill_color: str = "white", 
                           outline_color: str = "black", outline_width: int = 3):
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=fill_color)

def create_meme(image: Image.Image, text: str) -> Image.Image:
    img = resize_image(image)
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    draw = ImageDraw.Draw(img)
    img_width, img_height = img.size
    
    padding = 20
    max_text_width = img_width - (padding * 2)
    
    font_size = max(24, img_width // 10)
    font = get_font(font_size)
    
    lines = wrap_text(text.upper(), font, max_text_width, draw)
    
    while len(lines) > 4 and font_size > 16:
        font_size -= 4
        font = get_font(font_size)
        lines = wrap_text(text.upper(), font, max_text_width, draw)
    
    line_height = font_size + 5
    total_text_height = len(lines) * line_height
    
    start_y = img_height - total_text_height - padding
    
    for i, line in enumerate(lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
        except:
             text_width = draw.textlength(line, font=font)
             
        x = (img_width - text_width) // 2
        y = start_y + (i * line_height)
        
        draw_text_with_outline(draw, (x, y), line, font)
    
    return img

# --- Funções de IA (Gemini 1.5 FLASH - Mais Rápido e Estável) ---

def generate_meme_phrases(api_key: str, image: Image.Image, context: str) -> list:
    try:
        genai.configure(api_key=api_key)
        # Trocamos PRO por FLASH para garantir compatibilidade
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        prompt = f"""
        Atue como um especialista em memes.
        Analise esta imagem e o contexto: '{context}'.
        Crie 20 frases curtas, engraçadas e virais para memes com essa imagem.
        Responda APENAS com um JSON puro (lista de strings).
        Exemplo: ["Frase 1", "Frase 2"]
        """
        
        response = model.generate_content([prompt, image])
        
        text_clean = response.text.replace("```json", "").replace("```", "").strip()
        phrases = json.loads(text_clean)
        
        return phrases[:20] if isinstance(phrases, list) else []
        
    except Exception as e:
        st.error(f"Erro na IA: {str(e)}")
        return []

def iterate_meme_phrases(api_key: str, image: Image.Image, context: str, selected_phrases: list) -> list:
    try:
        genai.configure(api_key=api_key)
        # Trocamos PRO por FLASH aqui também
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        examples = "\n".join([f"- {p}" for p in selected_phrases])
        
        prompt = f"""
        Contexto: '{context}'.
        O usuário GOSTOU dessas frases:
        {examples}
        
        Crie MAIS 20 frases novas no mesmo estilo.
        Responda APENAS com JSON (lista de strings).
        """
        
        response = model.generate_content([prompt, image])
        
        text_clean = response.text.replace("```json", "").replace("```", "").strip()
        phrases = json.loads(text_clean)
        
        return phrases[:20] if isinstance(phrases, list) else []
        
    except Exception as e:
        st.error(f"Erro na Iteração: {str(e)}")
        return []

# --- Interface Principal ---

with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("Google Gemini API Key", type="password")
    st.markdown
