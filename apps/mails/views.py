"""
API Views for Email Management System
REST API endpoints for template management, SMTP configuration, notification rules, and analytics
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
import logging

from .models import (
    EmailTemplate,
    EmailSetting,
    SMTPConfiguration,
    NotificationRule,
    EmailLog
)
from .serializers import (
    EmailTemplateListSerializer,
    EmailTemplateSerializer,
    EmailSettingSerializer,
    SMTPConfigurationSerializer,
    NotificationRuleListSerializer,
    NotificationRuleSerializer,
    EmailLogListSerializer,
    EmailLogDetailSerializer,
    EmailPreviewSerializer,
    TestEmailSerializer,
    SMTPTestSerializer,
    BulkRuleUpdateSerializer,
    EmailAnalyticsDashboardSerializer,
)
from .permissions import (
    IsSuperUserForSMTP,
    IsStaffForTemplates,
    IsSuperUserForDeletion
)
from .services import EmailService, TemplateService, AnalyticsService
from .smtp_manager import SMTPManager

logger = logging.getLogger(__name__)


class EmailTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Email Template CRUD operations.
    
    Endpoints:
    - GET /api/admin/mails/templates/ - List templates
    - POST /api/admin/mails/templates/ - Create template
    - GET /api/admin/mails/templates/:id/ - Get template
    - PUT /api/admin/mails/templates/:id/ - Update template
    - DELETE /api/admin/mails/templates/:id/ - Delete template (superuser only)
    - POST /api/admin/mails/templates/:id/clone/ - Clone template
    - POST /api/admin/mails/templates/:id/preview/ - Preview template
    """
    queryset = EmailTemplate.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsStaffForTemplates]
    
    def get_serializer_class(self):
        """Use list serializer for list action, full serializer for others"""
        if self.action == 'list':
            return EmailTemplateListSerializer
        return EmailTemplateSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = EmailTemplate.objects.all()
        
        # Search
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(slug__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Filter by template type
        template_type = self.request.query_params.get('template_type', None)
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by language
        language_code = self.request.query_params.get('language_code', None)
        if language_code:
            queryset = queryset.filter(language_code=language_code)
        
        # Filter by template group
        template_group = self.request.query_params.get('template_group', None)
        if template_group:
            queryset = queryset.filter(template_group=template_group)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """Only superusers can delete templates"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can delete templates.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """
        Clone an existing template.
        
        POST /api/admin/mails/templates/:id/clone/
        Body: {"name": "New Template Name"}
        """
        template = self.get_object()
        new_name = request.data.get('name', f"{template.name} (Copy)")
        
        try:
            cloned = TemplateService.clone_template(
                template_id=str(template.id),
                new_name=new_name,
                created_by=request.user
            )
            
            serializer = EmailTemplateSerializer(cloned)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error cloning template: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """
        Generate preview of template with provided or sample context.
        
        POST /api/admin/mails/templates/:id/preview/
        Body: {"context": {"user_name": "John", ...}}
        """
        template = self.get_object()
        serializer = EmailPreviewSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        context = serializer.validated_data.get('context', None)
        
        try:
            preview = EmailService.preview_template(
                template_id=str(template.id),
                context=context
            )
            
            return Response(preview, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SMTPConfigurationView(APIView):
    """
    View for SMTP configuration management (single active config).
    
    Endpoints:
    - GET /api/admin/mails/smtp/ - Get active SMTP config
    - PUT /api/admin/mails/smtp/ - Update SMTP config
    - POST /api/admin/mails/smtp/test-connection/ - Test connection
    - POST /api/admin/mails/smtp/send-test/ - Send test email
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperUserForSMTP]
    
    def get(self, request):
        """Get active SMTP configuration"""
        smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
        
        if not smtp_config:
            return Response(
                {'message': 'No SMTP configuration found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SMTPConfigurationSerializer(smtp_config)
        return Response(serializer.data)
    
    def put(self, request):
        """Update or create SMTP configuration"""
        smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
        
        if smtp_config:
            # Update existing
            serializer = SMTPConfigurationSerializer(smtp_config, data=request.data, partial=True)
        else:
            # Create new
            serializer = SMTPConfigurationSerializer(data=request.data)
        
        if serializer.is_valid():
            smtp_config = serializer.save()
            smtp_config.is_active = True
            smtp_config.save()
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """Test SMTP connection"""
        smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
        
        if not smtp_config:
            return Response(
                {'error': 'No active SMTP configuration found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        success, message = SMTPManager.test_connection(smtp_config)
        
        # Update test status
        smtp_config.test_status = 'success' if success else 'failed'
        smtp_config.last_tested_at = timezone.now()
        smtp_config.save(update_fields=['test_status', 'last_tested_at'])
        
        return Response({
            'success': success,
            'message': message,
            'tested_at': smtp_config.last_tested_at
        }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def send_test(self, request):
        """Send test email"""
        serializer = SMTPTestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        test_email = serializer.validated_data['test_email']
        
        # Get a test template or create simple test email
        smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
        
        if not smtp_config:
            return Response(
                {'error': 'No active SMTP configuration found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Send simple test email
        success, message = SMTPManager.send_email(
            smtp_config=smtp_config,
            to_email=test_email,
            subject='Test Email from SajiloWork Email System',
            html_content='<h1>Test Email</h1><p>This is a test email from the SajiloWork Email Management System.</p>',
            text_content='Test Email\n\nThis is a test email from the SajiloWork Email Management System.'
        )
        
        return Response({
            'success': success,
            'message': message,
            'recipient': test_email
        }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)


class SMTPTestConnectionView(APIView):
    """Test SMTP connection endpoint"""
    permission_classes = [permissions.IsAuthenticated, IsSuperUserForSMTP]
    
    def post(self, request):
        """Test SMTP connection"""
        smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
        
        if not smtp_config:
            return Response(
                {'error': 'No active SMTP configuration found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        success, message = SMTPManager.test_connection(smtp_config)
        
        # Update test status
        smtp_config.test_status = 'success' if success else 'failed'
        smtp_config.last_tested_at = timezone.now()
        smtp_config.save(update_fields=['test_status', 'last_tested_at'])
        
        return Response({
            'success': success,
            'message': message,
            'tested_at': smtp_config.last_tested_at
        }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)


class SMTPSendTestView(APIView):
    """Send test email endpoint"""
    permission_classes = [permissions.IsAuthenticated, IsSuperUserForSMTP]
    
    def post(self, request):
        """Send test email"""
        serializer = SMTPTestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        test_email = serializer.validated_data['test_email']
        
        smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
        
        if not smtp_config:
            return Response(
                {'error': 'No active SMTP configuration found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Send simple test email
        success, message = SMTPManager.send_email(
            smtp_config=smtp_config,
            to_email=test_email,
            subject='Test Email from SajiloWork Email System',
            html_content='<h1>Test Email</h1><p>This is a test email from the SajiloWork Email Management System.</p>',
            text_content='Test Email\n\nThis is a test email from the SajiloWork Email Management System.'
        )
        
        return Response({
            'success': success,
            'message': message,
            'recipient': test_email
        }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)


class EmailSettingView(APIView):
    """
    View for global email settings (singleton).
    
    Endpoints:
    - GET /api/admin/mails/settings/ - Get settings
    - PUT /api/admin/mails/settings/ - Update settings
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get(self, request):
        """Get email settings"""
        settings = EmailSetting.objects.first()
        
        if not settings:
            # Create default settings
            settings = EmailSetting.objects.create()
        
        serializer = EmailSettingSerializer(settings)
        return Response(serializer.data)
    
    def put(self, request):
        """Update email settings"""
        settings = EmailSetting.objects.first()
        
        if not settings:
            settings = EmailSetting.objects.create()
        
        serializer = EmailSettingSerializer(settings, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NotificationRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Notification Rule management.
    
    Endpoints:
    - GET /api/admin/mails/rules/ - List all rules (grouped by category)
    - PUT /api/admin/mails/rules/:id/ - Update rule
    - POST /api/admin/mails/rules/bulk-update/ - Bulk update rules
    """
    queryset = NotificationRule.objects.all()
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    http_method_names = ['get', 'put', 'patch']  # No create or delete
    
    def get_serializer_class(self):
        """Use list serializer for list, full for detail"""
        if self.action == 'list':
            return NotificationRuleListSerializer
        return NotificationRuleSerializer
    
    def list(self, request):
        """List rules grouped by category"""
        rules = NotificationRule.objects.all().order_by('event_category', 'event_name')
        
        # Group by category
        grouped = {}
        for rule in rules:
            category = rule.event_category
            if category not in grouped:
                grouped[category] = []
            
            serializer = NotificationRuleListSerializer(rule)
            grouped[category].append(serializer.data)
        
        return Response(grouped)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update notification rules.
        
        POST /api/admin/mails/rules/bulk-update/
        Body: {
            "category": "marketing",  // optional
            "email_enabled": false,
            "push_enabled": true,
            ...
        }
        """
        serializer = BulkRuleUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        category = data.pop('category', None)
        
        # Build queryset
        queryset = NotificationRule.objects.all()
        if category:
            queryset = queryset.filter(event_category=category)
        
        # Update rules
        updated_count = queryset.update(**data)
        
        logger.info(f"Bulk updated {updated_count} notification rules")
        
        return Response({
            'success': True,
            'updated_count': updated_count
        })


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Email Logs.
    
    Endpoints:
    - GET /api/admin/mails/logs/ - List logs with filters
    - GET /api/admin/mails/logs/:id/ - Get log details
    """
    queryset = EmailLog.objects.all()
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get_serializer_class(self):
        """Use list serializer for list, detail for retrieve"""
        if self.action == 'list':
            return EmailLogListSerializer
        return EmailLogDetailSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = EmailLog.objects.select_related(
            'recipient_user', 'template_used', 'smtp_config_used'
        ).all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by recipient email
        recipient_email = self.request.query_params.get('recipient_email', None)
        if recipient_email:
            queryset = queryset.filter(recipient_email__icontains=recipient_email)
        
        # Filter by template
        template_id = self.request.query_params.get('template_id', None)
        if template_id:
            queryset = queryset.filter(template_used_id=template_id)
        
        # Date range filter
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Search in subject
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search) |
                Q(recipient_email__icontains=search)
            )
        
        return queryset.order_by('-created_at')


class EmailAnalyticsDashboardView(APIView):
    """
    View for email analytics dashboard.
    
    GET /api/admin/mails/analytics/dashboard/
    Query params: date_from, date_to
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get(self, request):
        """Get dashboard analytics"""
        # Parse date range
        date_to_str = request.query_params.get('date_to', None)
        date_from_str = request.query_params.get('date_from', None)
        
        if date_to_str:
            date_to = timezone.datetime.fromisoformat(date_to_str.replace('Z', '+00:00'))
        else:
            date_to = timezone.now()
        
        if date_from_str:
            date_from = timezone.datetime.fromisoformat(date_from_str.replace('Z', '+00:00'))
        else:
            date_from = date_to - timedelta(days=30)
        
        # Get statistics
        stats = AnalyticsService.get_dashboard_stats(date_from, date_to)
        
        return Response({
            'summary': stats,
            'date_range': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            }
        })



class ContactSubmissionView(APIView):
    """
    Public endpoint for contact form submissions.
    
    POST /api/contact/
    Body: {"name": "...", "email": "...", "message": "..."}
    """
    permission_classes = []  # Allow anyone to submit
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'contact'
    
    def post(self, request):
        """Submit contact form"""
        from .serializers import ContactSubmissionSerializer
        from .models import ContactSubmission
        
        serializer = ContactSubmissionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get client IP and user agent
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Save submission
        submission = serializer.save(
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Send notification email to admin (optional)
        try:
            from .smtp_manager import SMTPManager
            from .models import SMTPConfiguration, EmailSetting
            
            smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
            email_settings = EmailSetting.objects.first()
            
            if smtp_config and email_settings:
                from .contact_email_templates import (
                    build_contact_submission_html,
                    build_contact_submission_subject,
                    build_contact_submission_text,
                )

                admin_email = email_settings.support_email
                subject = build_contact_submission_subject(submission.name)
                html_content = build_contact_submission_html(
                    name=submission.name,
                    email=submission.email,
                    message=submission.message,
                    submitted_at=submission.created_at,
                    ip_address=submission.ip_address,
                )
                text_content = build_contact_submission_text(
                    name=submission.name,
                    email=submission.email,
                    message=submission.message,
                    submitted_at=submission.created_at,
                    ip_address=submission.ip_address,
                )

                SMTPManager.send_email(
                    smtp_config=smtp_config,
                    to_email=admin_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                )
        except Exception as e:
            logger.error(f"Failed to send admin notification email: {e}")
            # Don't fail the request if email fails
        
        return Response({
            'success': True,
            'message': 'Thank you for contacting us. We will get back to you soon.',
            'submission_id': str(submission.id)
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
