import streamlit as st
import json
import io
import zipfile
import re
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai # <--- CORREÇÃO AQUI (Biblioteca Padrão)

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
    # Tenta encontrar fontes boas no servidor Linux do Streamlit
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
        # draw.textbbox é o método moderno, mas vamos usar fallback se der erro
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
        exceptAttributeError:
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
    # Desenha o contorno (stroke) manualmente para ficar grosso
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=fill_color)

def create_meme(image: Image.Image, text: str) -> Image.Image:
    # Prepara a imagem
    img = resize_image(image)
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    draw = ImageDraw.Draw(img)
    img_width, img_height = img.size
    
    padding = 20
    max_text_width = img_width - (padding * 2)
    
    # Lógica de tamanho de fonte dinâmico
    font_size = max(24, img_width // 10) # Fonte maior para impacto
    font = get_font(font_size)
    
    lines = wrap_text(text.upper(), font, max_text_width, draw)
    
    # Se o texto for muito grande, diminui a fonte
    while len(lines) > 4 and font_size > 16:
        font_size -= 4
        font = get_font(font_size)
        lines = wrap_text(text.upper(), font, max_text_width, draw)
    
    line_height = font_size + 5
    total_text_height = len(lines) * line_height
    
    # Posiciona sempre embaixo (Clássico) ou ajusta se cobrir muito
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

# --- Funções de IA (Gemini V1 Stable) ---

def generate_meme_phrases(api_key: str, image: Image.Image, context: str) -> list:
    try:
        # Configuração da V1
        genai.configure(api_key=api_key)
        # Usando o modelo PRO para melhor criatividade
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""
        Atue como um especialista em memes brasileiros.
        Analise esta imagem e o contexto: '{context}'.
        
        Sua tarefa: Criar 20 frases curtas, hilárias e virais para memes com essa imagem.
        O tom deve ser adequado ao contexto fornecido.
        
        IMPORTANTE: Responda APENAS com um JSON puro (lista de strings).
        Exemplo: ["Quando o boleto vence", "Eu na segunda-feira"]
        """
        
        # Na V1 passamos a imagem PIL direto
        response = model.generate_content([prompt, image])
        
        # Limpeza do JSON
        text_clean = response.text.replace("```json", "").replace("```", "").strip()
        phrases = json.loads(text_clean)
        
        return phrases[:20] if isinstance(phrases, list) else []
        
    except Exception as e:
        st.error(f"Erro na IA: {str(e)}")
        return []

def iterate_meme_phrases(api_key: str, image: Image.Image, context: str, selected_phrases: list) -> list:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        examples = "\n".join([f"- {p}" for p in selected_phrases])
        
        prompt = f"""
        Contexto: '{context}'.
        O usuário GOSTOU dessas frases:
        {examples}
        
        Com base nesse gosto, crie MAIS 20 frases novas seguindo o mesmo estilo de humor.
        Não repita as anteriores.
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
    st.markdown("---")
    uploaded_file = st.file_uploader("Escolha uma imagem", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.session_state.original_image = image
        st.image(image, caption="Preview", use_column_width=True)

st.markdown("### 📝 Contexto")
context = st.text_area("Descreva o contexto (Ex: Corporativo, Festa, Ironia...)", height=80)

if st.button("🚀 Gerar Ideias", type="primary", use_container_width=True):
    if not api_key or not uploaded_file or not context:
        st.warning("Preencha a API Key, suba a imagem e dê um contexto!")
    else:
        with st.spinner("O robô está pensando nas piadas..."):
            phrases = generate_meme_phrases(api_key, st.session_state.original_image, context)
            if phrases:
                st.session_state.meme_phrases = phrases
                st.session_state.selected_phrases = {i: True for i in range(len(phrases))}
                st.success("Gerado!")

# --- Área de Seleção e Download ---

if st.session_state.meme_phrases:
    st.markdown("---")
    st.subheader("Selecione as melhores:")
    
    # Checkboxes em colunas
    cols = st.columns(2)
    for i, phrase in enumerate(st.session_state.meme_phrases):
        col_idx = i % 2
        with cols[col_idx]:
            st.session_state.selected_phrases[i] = st.checkbox(
                phrase, 
                value=st.session_state.selected_phrases.get(i, True),
                key=f"chk_{st.session_state.iteration_count}_{i}"
            )
    
    # Contagem
    selected_list = [
        st.session_state.meme_phrases[i] 
        for i, sel in st.session_state.selected_phrases.items() if sel
    ]
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        # Botão Iterar
        if st.button("🔄 Quero mais nesse estilo", use_container_width=True):
            if not selected_list:
                st.warning("Selecione pelo menos uma frase modelo!")
            else:
                with st.spinner("Criando variações..."):
                    new_phrases = iterate_meme_phrases(
                        api_key, st.session_state.original_image, context, selected_list
                    )
                    if new_phrases:
                        st.session_state.iteration_count += 1
                        st.session_state.meme_phrases = new_phrases
                        st.session_state.selected_phrases = {i: True for i in range(len(new_phrases))}
                        st.rerun()

    with c2:
        # Botão Download
        if st.button(f"💾 Baixar {len(selected_list)} Memes", type="primary", use_container_width=True):
            if not selected_list:
                st.error("Selecione alguma frase!")
            else:
                zip_buffer = io.BytesIO()
                prog_bar = st.progress(0)
                
                with zipfile.ZipFile(zip_buffer, 'w') as zf:
                    for idx, phrase in enumerate(selected_list):
                        # Gera a imagem final
                        final_img = create_meme(st.session_state.original_image, phrase)
                        
                        # Salva no buffer
                        img_byte_arr = io.BytesIO()
                        final_img.save(img_byte_arr, format='JPEG', quality=95)
                        
                        # Nome limpo para o arquivo
                        safe_name = re.sub(r'[^\w\s-]', '', phrase[:20]).strip().replace(' ', '_')
                        zf.writestr(f"meme_{idx+1}_{safe_name}.jpg", img_byte_arr.getvalue())
                        prog_bar.progress((idx + 1) / len(selected_list))
                
                st.success("Pronto!")
                st.download_button(
                    label="⬇️ CLIQUE PARA BAIXAR O ZIP",
                    data=zip_buffer.getvalue(),
                    file_name="meus_memes.zip",
                    mime="application/zip",
                    type="primary"
                )
