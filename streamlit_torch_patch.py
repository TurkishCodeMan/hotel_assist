#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streamlit-PyTorch uyumluluk düzeltmesi

Bu script, Streamlit'in PyTorch ile ilgili sorunlarını çözer.
Özellikle local_sources_watcher.py'nin PyTorch sınıflarını izlerken 
ortaya çıkan "no running event loop" hatasını giderir.

Kullanımı:
1. Bu dosyayı projenizin ana dizinine kaydedin
2. Streamlit uygulamanızı çalıştırmadan önce import edin:
   ```
   import streamlit_torch_patch
   import streamlit as st
   ```
"""

import sys
import logging
from importlib.util import find_spec

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_module_installed(module_name):
    """Bir modülün yüklü olup olmadığını kontrol eder."""
    try:
        return find_spec(module_name) is not None
    except ImportError:
        return False

def apply_streamlit_patch():
    """Streamlit'in PyTorch ile ilgili modül izleme sorunlarını düzeltir."""
    
    if not is_module_installed('streamlit'):
        logger.warning("Streamlit yüklü değil. Patch uygulanmadı.")
        return False
    
    try:
        # Streamlit'in local_sources_watcher modülünü import et
        import streamlit.watcher.local_sources_watcher as local_sources_watcher
        
        # Orijinal get_module_paths fonksiyonunu sakla
        original_get_module_paths = local_sources_watcher.get_module_paths
        
        # PyTorch ile ilgili modülleri filtrelemek için wrapper fonksiyonu
        def patched_get_module_paths(module):
            """
            PyTorch modüllerini es geçen düzeltilmiş get_module_paths fonksiyonu
            """
            # Modül adı kontrolleri - PyTorch ilgili modülleri atla
            module_name = getattr(module, "__name__", "")
            
            if module_name.startswith(("torch", "_torch")):
                logger.debug(f"PyTorch modülü atlandı: {module_name}")
                return []
            
            try:
                # Orijinal fonksiyonu çağır
                return original_get_module_paths(module)
            except RuntimeError as e:
                # "no running event loop" hatası veya diğer RuntimeError'lar
                if "no running event loop" in str(e) or "does not exist" in str(e):
                    logger.debug(f"Modül yollarını alırken hata atlandı: {module_name} - {e}")
                    return []
                # Bilinmeyen hatalar için yeniden yükselt
                raise
            
        # Fonksiyonu patch ile değiştir
        local_sources_watcher.get_module_paths = patched_get_module_paths
        
        logger.info("Streamlit-PyTorch uyumluluk düzeltmesi başarıyla uygulandı")
        return True
        
    except Exception as e:
        logger.error(f"Streamlit patch uygulanırken hata oluştu: {e}")
        return False

# Patch'i otomatik olarak uygula
patch_success = apply_streamlit_patch()

# Export değişkenleri
__all__ = ['apply_streamlit_patch', 'patch_success'] 