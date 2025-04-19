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
    
    Args:
        output_file (str): Çıktı dosyasının adı
        theme (str): Tema ('default', 'forest', 'dark', 'neutral')
        show_source (bool): Mermaid kaynak kodunu gösterme
        verbose (bool): Ayrıntılı log gösterme
    """
    # Grafiği oluştur
    workflow = build_graph()
    graph = workflow.get_graph()
    
    # Mermaid kaynak kodunu oluştur
    mermaid_source = graph.draw_mermaid()
    
    # Dosyaya kaydet
    with open(output_file, "w") as f:
        # Grafik direktifini ve yönünü ayarla (grafik öncesi tanımlar)
        graph_header = """graph TD
    __start__["Başlangıç"]
    reservation_agent["Rezervasyon Ajanı"]
    data_extractor["Veri Çıkarıcı"]
    router["Yönlendirici"]
    fetch_reservations_tool["Rezervasyon Listeleme"] 
    add_reservation_tool["Rezervasyon Ekleme"]
    update_reservation_tool["Rezervasyon Güncelleme"]
    delete_reservation_tool["Rezervasyon Silme"]
    check_availability_tool["Müsaitlik Kontrolü"]
    end_node["Bitiş"]
    __end__["Son"]
    
"""
        
        # Başlangıç düğümüne bağlantı - Düzeltilmiş akış yapısı
        connections = """    __start__ --> reservation_agent
    add_reservation_tool --> reservation_agent
    check_availability_tool --> reservation_agent
    data_extractor --> router
    delete_reservation_tool --> reservation_agent
    end_node --> __end__
    fetch_reservations_tool --> reservation_agent
    update_reservation_tool --> reservation_agent
    reservation_agent --> end_node
    
    reservation_agent -. Analiz Et .-> data_extractor
    reservation_agent -. Sonlandır .-> end_node
    router -. Listele .-> fetch_reservations_tool
    router -. Ekle .-> add_reservation_tool
    router -. Güncelle .-> update_reservation_tool
    router -. Sil .-> delete_reservation_tool
    router -. Kontrol Et .-> check_availability_tool
    router -. Sonlandır .-> end_node
"""
        
        # Stil tanımlamaları
        style_definitions = """    style __start__ fill:#58c4dc,stroke:#333,stroke-width:1px
    style __end__ fill:#ff9e9e,stroke:#333,stroke-width:1px
    style end_node fill:#ff9e9e,stroke:#333,stroke-width:1px
    style reservation_agent fill:#f2f0ff,stroke:#333,stroke-width:1px
    style data_extractor fill:#f2f0ff,stroke:#333,stroke-width:1px
    style router fill:#f2f0ff,stroke:#333,stroke-width:1px
    style fetch_reservations_tool fill:#f2f0ff,stroke:#333,stroke-width:1px
    style add_reservation_tool fill:#f2f0ff,stroke:#333,stroke-width:1px
    style update_reservation_tool fill:#f2f0ff,stroke:#333,stroke-width:1px
    style delete_reservation_tool fill:#f2f0ff,stroke:#333,stroke-width:1px
    style check_availability_tool fill:#f2f0ff,stroke:#333,stroke-width:1px 
"""
        
        # Özel Mermaid grafiği oluştur
        custom_mermaid = graph_header + connections + style_definitions
        f.write(custom_mermaid)
    
    if verbose:
        print(f"Graf görselleştirmesi '{output_file}' dosyasına kaydedildi.")
    
    if show_source:
        with open(output_file, "r") as f:
            custom_source = f.read()
            print("\nÖzel Mermaid kaynak kodu:")
            print(custom_source)
    
    # LangGraph tarafından oluşturulan orijinal kodu da kaydet
    if output_file.endswith(".mmd"):
        original_file = output_file.replace(".mmd", "_original.mmd")
        with open(original_file, "w") as f:
            f.write(mermaid_source)
        if verbose:
            print(f"Orijinal LangGraph görselleştirmesi '{original_file}' dosyasına kaydedildi.")
    
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
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"PNG dönüştürme hatası: {result.stderr}")
            return None
        
        logger.info(f"PNG dönüştürme başarılı: {png_file}")
        return png_file
        
    except Exception as e:
        logger.error(f"PNG dönüştürme işleminde hata: {str(e)}")
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
        show_source (bool): Mermaid kaynak kodunu gösterme
        background (str): PNG arka plan rengi
        verbose (bool): Ayrıntılı log gösterme
        
    Returns:
        dict: Oluşturulan dosya yolları
    """
    result_files = {}
    
    # MMD formatı isteniyorsa
    if format in ["mmd", "both"]:
        mmd_file = f"{output_name}.mmd"
        visualize_graph(
            output_file=mmd_file,
            theme=theme, 
            show_source=show_source,
            verbose=verbose
        )
        result_files["mmd"] = mmd_file
    
    # PNG formatı isteniyorsa
    if format in ["png", "both"]:
        # Eğer MMD oluşturulmadıysa, önce oluştur
        if format == "png":
            mmd_file = f"{output_name}.mmd"
            visualize_graph(
                output_file=mmd_file,
                theme=theme, 
                show_source=False,
                verbose=False
            )
        
        # PNG'ye dönüştür
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
        
        # Eğer sadece PNG isteniyorsa ve MMD geçici oluşturulduysa, sil
        if format == "png" and os.path.exists(mmd_file):
            try:
                if verbose:
                    print(f"Geçici MMD dosyası '{mmd_file}' siliniyor...")
                os.remove(mmd_file)
            except:
                pass
    
    return result_files

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LangGraph görselleştirme aracı")
    parser.add_argument("-o", "--output", default="ajan_grafi", help="Çıktı dosyası adı (uzantısız)")
    parser.add_argument("-f", "--format", default="both", choices=["mmd", "png", "both"], help="Çıktı formatı")
    parser.add_argument("-t", "--theme", default="default", choices=["default", "forest", "dark", "neutral"], help="Tema")
    parser.add_argument("-w", "--width", type=int, default=1200, help="PNG genişliği")
    parser.add_argument("-H", "--height", type=int, default=800, help="PNG yüksekliği")
    parser.add_argument("-b", "--background", default="#ffffff", help="PNG arka plan rengi")
    parser.add_argument("-s", "--show-source", action="store_true", help="Mermaid kaynak kodunu göster")
    parser.add_argument("-v", "--verbose", action="store_true", help="Ayrıntılı log")
    
    args = parser.parse_args()
    
    # Grafiği oluştur
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