"""
User models for the Airtasker marketplace.
Includes custom User model with roles, profiles, and verification.
"""
import uuid
from decimal import Decimal
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from .badge_catalog import ALL_BADGE_TYPE_CHOICES


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError('Users must have an email address')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for Airtasker marketplace.
    Supports multiple user roles: customer, tasker, admin.
    """
    
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('tasker', 'Tasker'),
        ('admin', 'Admin'),
    ]
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    google_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text='Google account subject id for OAuth login.',
    )
    facebook_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text='Facebook user id for OAuth login.',
    )
    username = models.CharField(max_length=150, unique=True, db_index=True, null=True, blank=True)
    username_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the user last changed their username (6-month cooldown applies).',
    )

    # Profile fields
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    
    # Bio and description
    bio = models.TextField(blank=True, help_text="Short bio about the user")
    tagline = models.CharField(max_length=255, blank=True, help_text="Professional tagline")
    
    # Profile media (Cloudinary URL or local media path)
    profile_image = models.CharField(
        max_length=2048,
        blank=True,
        default='',
        help_text='Profile image URL (Cloudinary) or local media path',
    )
    cover_image = models.CharField(
        max_length=2048,
        blank=True,
        default='',
        help_text='Cover image URL (Cloudinary) or local media path',
    )
    
    # Role and permissions
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Verification status
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    identity_verified = models.BooleanField(default=False)
    is_verified_tasker = models.BooleanField(default=False)
    has_payment_method = models.BooleanField(default=False, help_text="Whether user has linked a payment method")
    
    # Location
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Ratings and statistics
    average_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(5.00)]
    )
    total_reviews = models.PositiveIntegerField(default=0)
    trust_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)],
        help_text='Composite trust score (0–100) from ratings, completion, disputes',
    )
    tasks_completed = models.PositiveIntegerField(default=0)
    tasks_posted = models.PositiveIntegerField(default=0)
    
    # Tasker-specific fields
    hourly_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Hourly rate for tasker services"
    )
    response_time = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Average response time in minutes"
    )
    completion_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)],
        help_text="Task completion rate percentage"
    )
    
    # Account status
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    account_suspended = models.BooleanField(default=False)
    suspended_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When an automatic suspension ends (null = manual / indefinite).',
    )
    suspension_reason = models.TextField(blank=True)
    
    # Preferences
    notification_enabled = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    # Financial
    wallet_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Current wallet balance"
    )
    total_earned = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Total amount earned (for taskers)"
    )
    total_spent = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Total amount spent (for customers)"
    )
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='referrals'
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
            models.Index(fields=['city', 'country']),
            models.Index(fields=['average_rating']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        """Return the user's first name."""
        return self.first_name or self.email.split('@')[0]
    
    @property
    def is_customer(self):
        """Check if user is a customer."""
        return self.role == 'customer'
    
    @property
    def is_tasker(self):
        """Check if user is a tasker."""
        return self.role == 'tasker'
    
    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == 'admin'
    
    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [self.address, self.city, self.state, self.postal_code, self.country]
        return ', '.join(filter(None, parts))
    
    def update_online_status(self, is_online=True):
        """Update user's online status."""
        self.is_online = is_online
        self.last_seen = timezone.now()
        self.save(update_fields=['is_online', 'last_seen'])
    
    def update_rating(self):
        """Recalculate average rating and trust score from published reviews."""
        from apps.reviews.services import ReviewService

        ReviewService.update_user_profile_stats(self)


class UserSkill(models.Model):
    """Skills associated with taskers."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)
    details = models.TextField(blank=True, default='')
    category = models.CharField(max_length=100, blank=True)
    proficiency_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('expert', 'Expert'),
        ],
        default='intermediate'
    )
    years_of_experience = models.PositiveIntegerField(default=0)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_skills'
        unique_together = ['user', 'name']
        ordering = ['-verified', '-years_of_experience']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.name}"


class UserBadge(models.Model):
    """Badges and achievements for users."""

    BADGE_TYPES = ALL_BADGE_TYPE_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge_type = models.CharField(max_length=50, choices=BADGE_TYPES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_url = models.URLField(blank=True, null=True)
    verification_document = models.CharField(
        max_length=2048,
        blank=True,
        default='',
        help_text='Uploaded certificate or police check document URL (Cloudinary) or local path.',
    )
    document_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Licence or certificate number (optional).',
    )
    is_verified = models.BooleanField(
        default=False,
        help_text='When true, badge shows as active on the tasker profile.',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    earned_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        from .badge_catalog import BADGE_CATALOG

        if not self.name and self.badge_type != 'custom_licence':
            entry = BADGE_CATALOG.get(self.badge_type)
            if entry:
                self.name, self.description = entry[0], entry[1]
        if self.is_verified and self.verified_at is None:
            self.verified_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'user_badges'
        unique_together = ['user', 'badge_type', 'name']
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.name}"


KYC_DOCUMENT_TYPES = (
    'id_card',
    'passport',
    'driver_license',
    'proof_of_address',
    'police_check',
)


class UserKYC(models.Model):
    """Identity Trust Program — government ID verification for dashboard settings."""

    STATUS_CHOICES = [
        ('not_started', 'Not started'),
        ('pending', 'Pending review'),
        ('under_review', 'Under review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='kyc',
    )
    pan_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='Permanent Account Number (PAN) submitted with identity verification.',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started',
        db_index=True,
    )
    admin_notes = models.TextField(
        blank=True,
        help_text='Internal notes for admins (not shown to the user).',
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text='Reason shown to the user when verification is rejected.',
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kyc_reviews',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_kyc'
        verbose_name = 'KYC'
        verbose_name_plural = 'KYC'

    def __str__(self):
        return f"KYC — {self.user.email} ({self.get_status_display()})"


class UserDocument(models.Model):
    """KYC and verification documents."""
    
    DOCUMENT_TYPES = [
        ('id_card', 'ID Card'),
        ('passport', 'Passport'),
        ('driver_license', 'Driver License'),
        ('proof_of_address', 'Proof of Address'),
        ('business_license', 'Business License'),
        ('certificate', 'Certificate'),
        ('police_check', 'Police Check'),
        ('electrical_licence', 'Electrical Licence'),
        ('plumbing_licence', 'Plumbing Licence'),
        ('custom_licence', 'Custom Licence / Certificate'),
        ('portfolio', 'Portfolio Item'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    document_url = models.URLField()
    document_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_documents'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_document_type_display()}"


class PortfolioItem(models.Model):
    """Portfolio items for taskers to showcase their work."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolio_items')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.URLField(help_text="URL to the portfolio file")
    file_type = models.CharField(max_length=100, help_text="MIME type of the file")
    file_size = models.PositiveIntegerField(help_text="File size in bytes", default=0)
    thumbnail = models.URLField(blank=True, null=True, help_text="Thumbnail URL for images")
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portfolio_items'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['user', 'order']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.title}"


class UserFollow(models.Model):
    """A user follows another user (poster / tasker)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_following',
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_followers',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_follows'
        unique_together = [['follower', 'following']]
        indexes = [
            models.Index(fields=['follower', 'following']),
            models.Index(fields=['following']),
        ]

    def __str__(self):
        return f"{self.follower_id} follows {self.following_id}"


class EmployerProfile(models.Model):
    """Public business profile for employer (customer) accounts."""

    ACCOUNT_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('company', 'Company'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employer_profile',
    )
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default='individual',
    )
    company_name = models.CharField(max_length=255, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    team_size = models.CharField(max_length=80, blank=True)
    website = models.URLField(blank=True)
    cost_range = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    logo_color = models.CharField(max_length=40, default='serif-m')
    logo_text = models.CharField(max_length=8, default='CO')
    logo_image = models.CharField(
        max_length=2048,
        blank=True,
        default='',
        help_text='Employer logo URL (Cloudinary) or local media path',
    )
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employer_profiles'
        indexes = [
            models.Index(fields=['account_type']),
            models.Index(fields=['is_public']),
        ]

    def __str__(self):
        return self.company_name or str(self.user_id)


class EmployerGalleryImage(models.Model):
    """Gallery images for an employer public profile."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name='gallery_images',
    )
    image = models.CharField(
        max_length=2048,
        help_text='Gallery image URL (Cloudinary) or local media path',
    )
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'employer_gallery_images'
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['profile', 'sort_order']),
        ]

    def __str__(self):
        return f'{self.profile_id} gallery {self.id}'
