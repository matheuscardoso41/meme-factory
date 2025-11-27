import streamlit as st
import json
import io
import zipfile
import base64
import re
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Meme Factory AI",
    page_icon="🎭",
    layout="wide"
)

st.title("🎭 Meme Factory AI")
st.markdown("Gere memes incríveis usando Inteligência Artificial!")

if "meme_phrases" not in st.session_state:
    st.session_state.meme_phrases = []
if "original_image" not in st.session_state:
    st.session_state.original_image = None
if "selected_phrases" not in st.session_state:
    st.session_state.selected_phrases = {}
if "iteration_count" not in st.session_state:
    st.session_state.iteration_count = 0


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
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/nix/store/*/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    
    try:
        import glob
        nix_fonts = glob.glob("/nix/store/*/share/fonts/**/*.ttf", recursive=True)
        bold_fonts = [f for f in nix_fonts if "Bold" in f or "bold" in f]
        if bold_fonts:
            return ImageFont.truetype(bold_fonts[0], size)
        if nix_fonts:
            return ImageFont.truetype(nix_fonts[0], size)
    except Exception:
        pass
    
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]
        
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


def create_meme(image: Image.Image, text: str, position: str = "bottom") -> Image.Image:
    img = resize_image(image)
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    draw = ImageDraw.Draw(img)
    img_width, img_height = img.size
    
    padding = 20
    max_text_width = img_width - (padding * 2)
    
    font_size = max(24, img_width // 15)
    font = get_font(font_size)
    
    lines = wrap_text(text.upper(), font, max_text_width, draw)
    
    while len(lines) > 4 and font_size > 16:
        font_size -= 2
        font = get_font(font_size)
        lines = wrap_text(text.upper(), font, max_text_width, draw)
    
    line_height = font_size + 5
    total_text_height = len(lines) * line_height
    
    if position == "top":
        start_y = padding
    elif position == "bottom":
        start_y = img_height - total_text_height - padding
    else:
        if total_text_height > img_height * 0.3:
            start_y = img_height - total_text_height - padding
        else:
            start_y = img_height - total_text_height - padding
    
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (img_width - text_width) // 2
        y = start_y + (i * line_height)
        
        draw_text_with_outline(draw, (x, y), line, font)
    
    return img


def generate_meme_phrases(api_key: str, image_bytes: bytes, context: str, mime_type: str = "image/jpeg") -> list:
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""Analise esta imagem e o contexto fornecido para criar memes.

Contexto e Tom de Voz: {context}

Você deve gerar EXATAMENTE 20 frases curtas e engraçadas para memes baseadas nesta imagem.
As frases devem ser criativas, engraçadas e adequadas para redes sociais.
Considere o contexto e tom de voz especificado.

IMPORTANTE: Responda APENAS com um array JSON válido contendo exatamente 20 strings.
Não inclua nenhum texto adicional, apenas o JSON.
Exemplo do formato esperado:
["Frase 1", "Frase 2", "Frase 3", ...]
"""
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
                prompt,
            ],
        )
        
        response_text = response.text if response.text else ""
        
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            phrases = json.loads(json_str)
            if isinstance(phrases, list) and len(phrases) > 0:
                return phrases[:20]
        
        return []
        
    except Exception as e:
        st.error(f"Erro ao gerar frases: {str(e)}")
        return []


def iterate_meme_phrases(api_key: str, image_bytes: bytes, context: str, selected_phrases: list, mime_type: str = "image/jpeg") -> list:
    try:
        client = genai.Client(api_key=api_key)
        
        selected_examples = "\n".join([f"- {phrase}" for phrase in selected_phrases])
        
        prompt = f"""Analise esta imagem e o contexto fornecido para criar mais memes.

Contexto e Tom de Voz: {context}

O usuário já selecionou estas frases como suas favoritas:
{selected_examples}

Com base no estilo e tom dessas frases selecionadas, gere MAIS 20 frases novas e diferentes.
As novas frases devem seguir o mesmo estilo de humor e abordagem das frases selecionadas.
Não repita nenhuma das frases já existentes.

IMPORTANTE: Responda APENAS com um array JSON válido contendo exatamente 20 strings novas.
Não inclua nenhum texto adicional, apenas o JSON.
Exemplo do formato esperado:
["Frase 1", "Frase 2", "Frase 3", ...]
"""
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
                prompt,
            ],
        )
        
        response_text = response.text if response.text else ""
        
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            phrases = json.loads(json_str)
            if isinstance(phrases, list) and len(phrases) > 0:
                return phrases[:20]
        
        return []
        
    except Exception as e:
        st.error(f"Erro ao iterar frases: {str(e)}")
        return []


with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input(
        "Google Gemini API Key",
        type="password",
        help="Insira sua chave de API do Google Gemini"
    )
    
    st.markdown("---")
    st.markdown("### 📤 Upload de Imagem")
    uploaded_file = st.file_uploader(
        "Escolha uma imagem (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
        help="Faça upload da imagem base para seus memes"
    )
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.session_state.original_image = image
        st.image(image, caption="Imagem carregada", use_container_width=True)

st.markdown("### 📝 Contexto e Tom de Voz")
context = st.text_area(
    "Descreva o contexto e o tom desejado para os memes",
    placeholder="Ex.: tom bem humorado, direcionado a um público de 24-35 anos, brasileiros. conteúdo deve ser posicionado para gerar ampla identificação e interesse.",
    height=100
)

col1, col2 = st.columns([1, 2])

with col1:
    generate_button = st.button(
        "🚀 Gerar 20 Ideias de Memes",
        type="primary",
        use_container_width=True,
        disabled=not (api_key and uploaded_file and context)
    )

if not api_key:
    st.info("👆 Insira sua API Key do Google Gemini na barra lateral")
elif not uploaded_file:
    st.info("👆 Faça upload de uma imagem na barra lateral")
elif not context:
    st.info("👆 Descreva o contexto e tom de voz desejado acima")

if generate_button and api_key and uploaded_file and context:
    with st.spinner("🤖 Analisando imagem e gerando frases criativas..."):
        uploaded_file.seek(0)
        image_bytes = uploaded_file.read()
        
        file_type = uploaded_file.type if uploaded_file.type else "image/jpeg"
        if uploaded_file.name:
            if uploaded_file.name.lower().endswith(".png"):
                file_type = "image/png"
            elif uploaded_file.name.lower().endswith((".jpg", ".jpeg")):
                file_type = "image/jpeg"
        
        phrases = generate_meme_phrases(api_key, image_bytes, context, file_type)
        
        if phrases:
            st.session_state.meme_phrases = phrases
            st.session_state.selected_phrases = {i: True for i in range(len(phrases))}
            st.success(f"✅ {len(phrases)} frases geradas com sucesso!")
        else:
            st.error("Não foi possível gerar as frases. Verifique sua API key e tente novamente.")

if st.session_state.meme_phrases:
    st.markdown("---")
    st.markdown("### 📋 Frases Geradas")
    st.markdown("Desmarque as frases que você não deseja usar:")
    
    cols = st.columns(2)
    
    for i, phrase in enumerate(st.session_state.meme_phrases):
        col_idx = i % 2
        with cols[col_idx]:
            checked = st.checkbox(
                phrase,
                value=st.session_state.selected_phrases.get(i, True),
                key=f"phrase_{st.session_state.iteration_count}_{i}"
            )
            st.session_state.selected_phrases[i] = checked
    
    selected_count = sum(1 for v in st.session_state.selected_phrases.values() if v)
    st.markdown(f"**{selected_count} frases selecionadas**")
    
    st.markdown("---")
    
    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        generate_images_button = st.button(
            "🎨 Gerar Imagens Selecionadas",
            type="primary",
            use_container_width=True,
            disabled=selected_count == 0 or st.session_state.original_image is None
        )
    
    with btn_col2:
        iterate_button = st.button(
            "🔄 Iterar (gerar mais ideias)",
            use_container_width=True,
            disabled=selected_count == 0 or not (api_key and uploaded_file and context)
        )
    
    if iterate_button and api_key and uploaded_file and context:
        selected_phrases_for_iteration = [
            st.session_state.meme_phrases[i] 
            for i, selected in st.session_state.selected_phrases.items() 
            if selected
        ]
        
        with st.spinner("🤖 Gerando mais ideias baseadas na sua seleção..."):
            uploaded_file.seek(0)
            image_bytes = uploaded_file.read()
            
            file_type = uploaded_file.type if uploaded_file.type else "image/jpeg"
            if uploaded_file.name:
                if uploaded_file.name.lower().endswith(".png"):
                    file_type = "image/png"
                elif uploaded_file.name.lower().endswith((".jpg", ".jpeg")):
                    file_type = "image/jpeg"
            
            new_phrases = iterate_meme_phrases(api_key, image_bytes, context, selected_phrases_for_iteration, file_type)
            
            if new_phrases:
                st.session_state.iteration_count += 1
                st.session_state.meme_phrases = new_phrases
                st.session_state.selected_phrases = {i: False for i in range(len(new_phrases))}
                st.success(f"✅ {len(new_phrases)} novas frases geradas!")
                st.rerun()
            else:
                st.error("Não foi possível gerar novas frases. Tente novamente.")
    
    if generate_images_button and st.session_state.original_image is not None:
        selected_phrases_list = [
            st.session_state.meme_phrases[i] 
            for i, selected in st.session_state.selected_phrases.items() 
            if selected
        ]
        
        if selected_phrases_list:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for idx, phrase in enumerate(selected_phrases_list):
                    status_text.text(f"Gerando meme {idx + 1} de {len(selected_phrases_list)}...")
                    progress_bar.progress((idx + 1) / len(selected_phrases_list))
                    
                    meme_image = create_meme(st.session_state.original_image, phrase)
                    
                    img_buffer = io.BytesIO()
                    meme_image.save(img_buffer, format="JPEG", quality=90)
                    img_buffer.seek(0)
                    
                    safe_filename = re.sub(r'[^\w\s-]', '', phrase[:30]).strip()
                    safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
                    filename = f"meme_{idx + 1:02d}_{safe_filename}.jpg"
                    
                    zip_file.writestr(filename, img_buffer.getvalue())
            
            zip_buffer.seek(0)
            
            progress_bar.empty()
            status_text.empty()
            
            st.success(f"✅ {len(selected_phrases_list)} memes gerados com sucesso!")
            
            st.markdown("### 📥 Download")
            st.download_button(
                label="⬇️ BAIXAR TODOS OS MEMES (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="memes_factory.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            with st.expander("👁️ Visualizar Memes Gerados"):
                preview_cols = st.columns(3)
                for idx, phrase in enumerate(selected_phrases_list[:6]):
                    with preview_cols[idx % 3]:
                        meme_preview = create_meme(st.session_state.original_image, phrase)
                        st.image(meme_preview, caption=phrase[:50] + "..." if len(phrase) > 50 else phrase)

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Meme Factory AI - Feito com ❤️ para seu time de marketing"
    "</div>",
    unsafe_allow_html=True
)
