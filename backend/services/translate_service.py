"""
Translation Service
Uses deep-translator to translate text (free, no API key needed)
"""
from deep_translator import GoogleTranslator
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TranslateService:
    """Service for translating text using free translation APIs"""
    
    def __init__(self):
        logger.info("TranslateService initialized")
    
    def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Translate a single text string.
        
        Args:
            text: Text to translate
            source_lang: Source language code (e.g., 'en')
            target_lang: Target language code (e.g., 'hi')
        
        Returns:
            (success, translated_text, error_message)
        """
        try:
            if not text.strip():
                return True, "", None
            
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated = translator.translate(text)
            
            return True, translated, None
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return False, None, str(e)
    
    def translate_segments(
        self,
        segments: List[Dict],
        source_lang: str,
        target_lang: str
    ) -> Tuple[bool, Optional[List[Dict]], Optional[str]]:
        """
        Translate a list of segments (with timestamps).
        
        Args:
            segments: List of segments with 'text', 'start', 'end' keys
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            (success, translated_segments, error_message)
        """
        try:
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated_segments = []
            
            # Batch translate for efficiency
            texts = [seg.get('text', '') for seg in segments]
            
            # Filter empty texts
            non_empty_indices = [i for i, t in enumerate(texts) if t.strip()]
            non_empty_texts = [texts[i] for i in non_empty_indices]
            
            # Translate non-empty texts
            if non_empty_texts:
                # Translate in batches of 50 to avoid rate limits
                batch_size = 50
                all_translated = []
                
                for i in range(0, len(non_empty_texts), batch_size):
                    batch = non_empty_texts[i:i + batch_size]
                    # Translate batch
                    translated_batch = translator.translate_batch(batch)
                    all_translated.extend(translated_batch)
                
                # Map translations back
                translation_map = dict(zip(non_empty_indices, all_translated))
            else:
                translation_map = {}
            
            # Build translated segments
            for i, seg in enumerate(segments):
                translated_text = translation_map.get(i, seg.get('text', ''))
                translated_segments.append({
                    'id': seg.get('id'),
                    'start': seg.get('start'),
                    'end': seg.get('end'),
                    'original_text': seg.get('text', ''),
                    'text': translated_text,
                })
            
            logger.info(f"Translated {len(segments)} segments from {source_lang} to {target_lang}")
            return True, translated_segments, None
            
        except Exception as e:
            logger.error(f"Segment translation failed: {e}")
            return False, None, str(e)
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        try:
            return GoogleTranslator().get_supported_languages(as_dict=True)
        except:
            # Fallback to common languages
            return {
                'english': 'en',
                'spanish': 'es',
                'french': 'fr',
                'german': 'de',
                'hindi': 'hi',
                'chinese (simplified)': 'zh-CN',
                'japanese': 'ja',
                'korean': 'ko',
                'arabic': 'ar',
                'portuguese': 'pt',
                'italian': 'it',
                'russian': 'ru',
            }
