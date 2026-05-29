"""
Uploads Services
Business logic for file uploads and processing.
"""
from django.core.files.base import ContentFile
from .models import Upload, ImageUpload, DocumentUpload
import os


class UploadService:
    """Service for handling file uploads and processing"""
    
    @staticmethod
    def process_upload(upload_id):
        """
        Process uploaded file (extract metadata, generate thumbnails, etc.)
        This would typically be called asynchronously via Celery.
        """
        try:
            upload = Upload.objects.get(id=upload_id)
            upload.status = 'processing'
            upload.save()
            
            # Process based on file type
            if upload.file_type == 'image':
                UploadService._process_image(upload)
            elif upload.file_type == 'document':
                UploadService._process_document(upload)
            
            upload.status = 'completed'
            upload.save()
            
        except Exception as e:
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
    
    @staticmethod
    def _process_image(upload):
        """
        Process image upload (extract dimensions, generate thumbnails).
        Requires Pillow package.
        """
        try:
            from PIL import Image
            
            # Open image
            img = Image.open(upload.file.path)
            
            # Create ImageUpload record
            image_upload = ImageUpload.objects.create(
                upload=upload,
                width=img.width,
                height=img.height,
                format=img.format,
                color_mode=img.mode,
                has_transparency='A' in img.mode
            )
            
            # Generate thumbnails
            UploadService._generate_thumbnails(image_upload, img)
            
            image_upload.thumbnails_generated = True
            image_upload.save()
            
        except ImportError:
            # Pillow not installed, skip image processing
            pass
        except Exception as e:
            raise Exception(f"Image processing failed: {str(e)}")
    
    @staticmethod
    def _generate_thumbnails(image_upload, img):
        """Generate thumbnail images"""
        try:
            from PIL import Image
            from io import BytesIO
            
            sizes = {
                'small': (150, 150),
                'medium': (300, 300),
                'large': (600, 600)
            }
            
            for size_name, size in sizes.items():
                # Create thumbnail
                thumb = img.copy()
                thumb.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save to BytesIO
                thumb_io = BytesIO()
                thumb.save(thumb_io, format=img.format or 'JPEG')
                thumb_io.seek(0)
                
                # Save to model field
                file_name = f"thumb_{size_name}_{image_upload.upload.file_name}"
                thumb_file = ContentFile(thumb_io.read(), name=file_name)
                
                if size_name == 'small':
                    image_upload.thumbnail_small = thumb_file
                elif size_name == 'medium':
                    image_upload.thumbnail_medium = thumb_file
                elif size_name == 'large':
                    image_upload.thumbnail_large = thumb_file
            
            image_upload.save()
            
        except Exception as e:
            raise Exception(f"Thumbnail generation failed: {str(e)}")
    
    @staticmethod
    def _process_document(upload):
        """
        Process document upload (extract text, metadata).
        Requires PyPDF2 or similar packages.
        """
        try:
            # Determine document type from extension
            ext = os.path.splitext(upload.file_name)[1].lower()
            
            doc_type_map = {
                '.pdf': 'pdf',
                '.doc': 'doc',
                '.docx': 'docx',
                '.xls': 'xls',
                '.xlsx': 'xlsx',
                '.ppt': 'ppt',
                '.pptx': 'pptx',
                '.txt': 'txt',
                '.csv': 'csv',
            }
            
            document_type = doc_type_map.get(ext, 'other')
            
            # Create DocumentUpload record
            document_upload = DocumentUpload.objects.create(
                upload=upload,
                document_type=document_type
            )
            
            # Extract text based on document type
            if document_type == 'pdf':
                UploadService._extract_pdf_text(document_upload)
            elif document_type == 'txt':
                UploadService._extract_txt_text(document_upload)
            
        except Exception as e:
            raise Exception(f"Document processing failed: {str(e)}")
    
    @staticmethod
    def _extract_pdf_text(document_upload):
        """Extract text from PDF (requires PyPDF2)"""
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(document_upload.upload.file.path)
            document_upload.page_count = len(reader.pages)
            
            # Extract text from all pages
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            
            document_upload.extracted_text = text[:10000]  # Limit to 10k chars
            document_upload.word_count = len(text.split())
            document_upload.text_extracted = True
            document_upload.save()
            
        except ImportError:
            # PyPDF2 not installed, skip text extraction
            pass
        except Exception as e:
            raise Exception(f"PDF text extraction failed: {str(e)}")
    
    @staticmethod
    def _extract_txt_text(document_upload):
        """Extract text from TXT file"""
        try:
            with open(document_upload.upload.file.path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            document_upload.extracted_text = text[:10000]  # Limit to 10k chars
            document_upload.word_count = len(text.split())
            document_upload.text_extracted = True
            document_upload.save()
            
        except Exception as e:
            raise Exception(f"TXT text extraction failed: {str(e)}")
    
    @staticmethod
    def validate_file_type(file, allowed_types):
        """Validate file type against allowed types"""
        ext = os.path.splitext(file.name)[1].lower()
        return ext in allowed_types
    
    @staticmethod
    def get_file_type_from_mime(mime_type):
        """Determine file type from MIME type"""
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type in ['application/pdf', 'application/msword', 
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'application/vnd.ms-excel',
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          'text/plain', 'text/csv']:
            return 'document'
        else:
            return 'other'
