import io
import re
import unicodedata
from pypdf import PdfReader
from datetime import datetime

class CertificadoService:
    @staticmethod
    def extract_text(pdf_bytes):
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""

    @staticmethod
    def normalize(text):
        if not text:
            return ""
        # Remove accents and lowercase
        text = unicodedata.normalize('NFD', text)
        text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
        return text.lower().strip()

    @classmethod
    def validate(cls, text, user_full_name, course_official_name, synonyms_str=""):
        """
        Returns (is_valid, observations)
        """
        text_norm = cls.normalize(text)
        user_name_norm = cls.normalize(user_full_name)
        
        # Prepare course names to check
        course_names = [course_official_name]
        if synonyms_str:
            synonyms = [s.strip() for s in synonyms_str.split(',') if s.strip()]
            course_names.extend(synonyms)
        
        course_norms = [cls.normalize(name) for name in course_names]
        
        reasons = []
        
        # 1. Name Validation
        name_parts = user_name_norm.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_names = name_parts[1:]
            
            has_first = first_name in text_norm
            has_any_last = any(last in text_norm for last in last_names)
            
            if not (has_first and has_any_last):
                reasons.append("Nome não encontrado ou incompleto no certificado.")
        else:
            if user_name_norm not in text_norm:
                reasons.append("Nome não encontrado no certificado.")

        # 2. Course Validation
        has_course = any(cn in text_norm for cn in course_norms)
        if not has_course:
            reasons.append(f"Nome do curso (ou sinônimo) não encontrado no certificado.")

        # 3. Date Validation (Current Semester)
        now = datetime.now()
        current_year = now.year
        is_first_semester = 1 <= now.month <= 6
        
        months_map = {
            "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
            "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
        }
        
        found_date = False
        # Patterns: 
        # 1: MM/DD/YYYY ou DD/MM/YYYY
        # 2: MM/YYYY
        # 3: Month de YYYY
        # 4: Month/YYYY
        # 5: DD Month YYYY (Cisco Style)
        date_pattern = re.compile(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})|(\d{1,2})[/\-](\d{4})|(\w+)\s+de\s+(\d{4})|(\w+)[/\-](\d{4})|(\d{1,2})\s+(\w+)\s+(\d{4})')
        matches = date_pattern.findall(text_norm)
        
        for m in matches:
            m_month = None
            m_year = None
            
            if m[0] and m[1] and m[2]: # MM/DD/YYYY ou DD/MM/YYYY
                # Tentamos inferir o mês (geralmente o primeiro ou segundo grupo se < 12)
                v1, v2 = int(m[0]), int(m[1])
                if v1 <= 12: m_month = v1
                elif v2 <= 12: m_month = v2
                m_year = int(m[2])
            elif m[3] and m[4]: # MM/YYYY
                m_month = int(m[3])
                m_year = int(m[4])
            elif m[5] and m[6]: # Month de YYYY
                m_month = months_map.get(m[5])
                m_year = int(m[6])
            elif m[7] and m[8]: # Month/YYYY
                m_month = months_map.get(m[7])
                m_year = int(m[8])
            elif m[9] and m[10] and m[11]: # DD Month YYYY
                m_month = months_map.get(m[10])
                m_year = int(m[11])
                
            if m_month and m_year:
                if m_year == current_year:
                    if is_first_semester and 1 <= m_month <= 6:
                        found_date = True
                        break
                    elif not is_first_semester and 7 <= m_month <= 12:
                        found_date = True
                        break
        
        if not found_date:
            semester_str = "1º semestre" if is_first_semester else "2º semestre"
            reasons.append(f"Data do certificado não condiz com o semestre atual ({semester_str} de {current_year}).")

        if not reasons:
            return True, ""
        else:
            return False, " | ".join(reasons)
