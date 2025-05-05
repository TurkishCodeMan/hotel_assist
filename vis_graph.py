from IPython.display import Image, display
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
from agent_graph.graph import build_graph, create_graph
import os
import subprocess
import logging

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('graph-visualizer')

def visualize_graph(output_file="complex_mermaid.mmd", theme="default", show_source=True, verbose=True):
    """
    LangGraph grafiğini oluşturur ve Mermaid formatında kaydeder.
    Artık grafiği build_graph() ile dinamik olarak oluşturur.
    
    Args:
        output_file (str): Çıktı dosyasının adı
        theme (str): Tema ('default', 'forest', 'dark', 'neutral') - PNG için kullanılır, MMD'yi etkilemez
        show_source (bool): Mermaid kaynak kodunu konsolda gösterme
        verbose (bool): Ayrıntılı log gösterme
    """
    # Grafiği oluştur
    workflow = build_graph()
    graph = workflow.get_graph()
    
    # Mermaid kaynak kodunu LangGraph'ten dinamik olarak al
    mermaid_source = graph.draw_mermaid()
    
    # Dosyaya kaydet
    with open(output_file, "w") as f:
        f.write(mermaid_source)
    
    if verbose:
        print(f"Dinamik graf görselleştirmesi '{output_file}' dosyasına kaydedildi.")
    
    if show_source:
        print("\nLangGraph tarafından oluşturulan Mermaid kaynak kodu:")
        print(mermaid_source)
        
    # Orijinal kod kaydetme kaldırıldı, zaten onu kullanıyoruz.
    
    return mermaid_source

def convert_to_png(mmd_file, png_file=None, width=1200, height=800, theme="default", background="#ffffff"):
    """
    Mermaid dosyasını PNG'ye dönüştürür
    
    Args:
        mmd_file (str): Mermaid dosyası
        png_file (str): PNG çıktı dosyası (belirtilmezse aynı isimle .png uzantılı olur)
        width (int): PNG genişliği
        height (int): PNG yüksekliği
        theme (str): Görselleştirme teması
        background (str): Arka plan rengi
        
    Returns:
        str: Oluşturulan PNG dosyasının tam yolu
    """
    # PNG dosya adını belirle
    if png_file is None:
        png_file = os.path.splitext(mmd_file)[0] + ".png"
    
    try:
        logger.info(f"PNG dönüştürme işlemi başlatılıyor: {mmd_file} -> {png_file}")
        
        # Mermaid CLI'yi çağır
        # 'mmdc' komutunun sistemde kurulu ve PATH içinde olması gerekir.
        command = [
            "mmdc",  # Mermaid CLI komutu
            "-i", mmd_file,
            "-o", png_file,
            "-w", str(width),
            "-H", str(height),
            "-b", background,
            "-t", theme
        ]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False # Hata durumunda exception fırlatmasın
        )
        
        if result.returncode != 0:
            # Hata mesajını logla ama None döndür
            logger.error(f"PNG dönüştürme hatası (mmdc): {result.stderr}")
            # Kullanıcıya mmdc'nin kurulu olup olmadığını kontrol etmesini önerebiliriz
            print("\nHATA: PNG dönüştürme başarısız. 'mmdc' (Mermaid CLI) komutunun sisteminizde kurulu ve erişilebilir olduğundan emin olun.")
            print("Kurulum için: npm install -g @mermaid-js/mermaid-cli")
            return None
        
        logger.info(f"PNG dönüştürme başarılı: {png_file}")
        return png_file
        
    except FileNotFoundError:
        logger.error("PNG dönüştürme hatası: 'mmdc' komutu bulunamadı. Mermaid CLI kurulu mu?")
        print("\nHATA: 'mmdc' komutu bulunamadı. Lütfen Mermaid CLI'nin kurulu olduğundan ve PATH ortam değişkeninde bulunduğundan emin olun.")
        print("Kurulum için: npm install -g @mermaid-js/mermaid-cli")
        return None
    except Exception as e:
        logger.error(f"PNG dönüştürme işleminde beklenmedik hata: {str(e)}")
        return None

def generate_graph(output_name="ajan_grafi", format="mmd", theme="default", width=1200, height=800, 
                  show_source=True, background="#ffffff", verbose=True):
    """
    Grafiği oluşturur ve istenen formatta çıktı alır
    
    Args:
        output_name (str): Çıktı dosyası adı (uzantısız)
        format (str): Çıktı formatı ('mmd', 'png' veya 'both')
        theme (str): Tema ('default', 'forest', 'dark', 'neutral')
        width (int): PNG genişliği
        height (int): PNG yüksekliği
        show_source (bool): Mermaid kaynak kodunu konsolda gösterme
        background (str): PNG arka plan rengi
        verbose (bool): Ayrıntılı log gösterme
        
    Returns:
        dict: Oluşturulan dosya yolları {'mmd': ..., 'png': ...}
    """
    result_files = {}
    mmd_file = f"{output_name}.mmd" # MMD dosyası her zaman oluşturulacak
    
    # MMD formatını oluştur
    visualize_graph(
        output_file=mmd_file,
        theme=theme, # MMD için tema gereksiz ama kalsın
        show_source=show_source if format != "png" else False, # Sadece PNG ise gösterme
        verbose=verbose
    )
    result_files["mmd"] = mmd_file
    
    # PNG formatı isteniyorsa
    if format in ["png", "both"]:
        png_file = f"{output_name}.png"
        png_result = convert_to_png(
            mmd_file=mmd_file,
            png_file=png_file,
            width=width,
            height=height,
            theme=theme,
            background=background
        )
        
        if png_result:
            result_files["png"] = png_file
            if verbose:
                print(f"PNG görselleştirmesi '{png_file}' dosyasına kaydedildi.")
        # PNG oluşturulamazsa MMD yine de kalır.
        
        # Eğer sadece PNG isteniyorsa ve MMD geçici oluşturulduysa, silme işlemini kaldırıyoruz
        # çünkü PNG oluşturma başarısız olabilir ve MMD'yi görmek isteyebiliriz.
        # Kullanıcı isterse MMD dosyasını manuel silebilir.
    
    return result_files

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LangGraph görselleştirme aracı")
    parser.add_argument("-o", "--output", default="ajan_grafi", help="Çıktı dosyası adı (uzantısız)")
    parser.add_argument("-f", "--format", default="both", choices=["mmd", "png", "both"], help="Çıktı formatı")
    parser.add_argument("-t", "--theme", default="default", choices=["default", "forest", "dark", "neutral"], help="PNG Tema")
    parser.add_argument("-w", "--width", type=int, default=1200, help="PNG genişliği")
    parser.add_argument("-H", "--height", type=int, default=800, help="PNG yüksekliği")
    parser.add_argument("-b", "--background", default="#ffffff", help="PNG arka plan rengi")
    parser.add_argument("-s", "--show-source", action="store_true", help="Mermaid kaynak kodunu konsolda göster")
    parser.add_argument("-v", "--verbose", action="store_true", help="Ayrıntılı log")
    
    args = parser.parse_args()
    
    # Grafiği oluştur ve belirtilen formatlarda kaydet
    generate_graph(
        output_name=args.output,
        format=args.format,
        theme=args.theme,
        width=args.width,
        height=args.height,
        show_source=args.show_source,
        background=args.background,
        verbose=args.verbose
    )