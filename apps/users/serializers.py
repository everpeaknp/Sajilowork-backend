"""
Serializers for User models.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.base_user import BaseUserManager
from django.core.exceptions import ValidationError
from .models import User, UserSkill, UserBadge, UserDocument, PortfolioItem


class UserSkillSerializer(serializers.ModelSerializer):
    """Serializer for user skills."""

    class Meta:
        model = UserSkill
        fields = [
            'id', 'name', 'category', 'proficiency_level',
            'years_of_experience', 'verified', 'created_at'
        ]
        read_only_fields = ['id', 'verified', 'created_at']

    def validate_name(self, value):
        value = (value or '').strip()
        if len(value) < 2:
            raise serializers.ValidationError('Skill name must be at least 2 characters.')
        return value

    def validate_category(self, value):
        return (value or 'skill').strip().lower()

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        name = attrs.get('name') or getattr(self.instance, 'name', None)
        if user and name and self.instance is None:
            if UserSkill.objects.filter(user=user, name__iexact=name.strip()).exists():
                raise serializers.ValidationError(
                    {'name': 'You already have a skill with this name.'}
                )
        return attrs


class UserBadgeSerializer(serializers.ModelSerializer):
    """Serializer for user badges."""

    user = serializers.UUIDField(source='user_id', read_only=True)
    created_at = serializers.DateTimeField(source='earned_at', read_only=True)
    verification_document = serializers.SerializerMethodField()

    class Meta:
        model = UserBadge
        fields = [
            'id',
            'user',
            'badge_type',
            'name',
            'description',
            'icon_url',
            'document_number',
            'verification_document',
            'is_verified',
            'verified_at',
            'earned_at',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'name',
            'description',
            'icon_url',
            'document_number',
            'verification_document',
            'is_verified',
            'verified_at',
            'earned_at',
            'created_at',
        ]

    def get_verification_document(self, obj):
        if not obj.verification_document:
            return None
        request = self.context.get('request')
        url = obj.verification_document.url
        if request and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url


class PublicUserBadgeSerializer(serializers.ModelSerializer):
    """Public profile: verified badges only, no private documents."""

    class Meta:
        model = UserBadge
        fields = ['id', 'badge_type', 'name', 'description', 'is_verified', 'verified_at']
        read_only_fields = fields


class UserBadgeCreateSerializer(serializers.Serializer):
    """Request a verification badge from the tasker dashboard."""

    badge_type = serializers.ChoiceField(
        choices=[
            'police_check',
            'payment_verified',
            'electrical_licence',
            'plumbing_licence',
            'custom_licence',
            'identity_verified',
        ]
    )
    name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )
    document_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
    )

    def validate(self, attrs):
        badge_type = attrs.get('badge_type')
        name = (attrs.get('name') or '').strip()
        if badge_type == 'custom_licence' and len(name) < 2:
            raise serializers.ValidationError(
                {'name': 'Enter a name for your custom licence or certification.'}
            )
        attrs['name'] = name
        return attrs


class UserDocumentSerializer(serializers.ModelSerializer):
    """Serializer for user documents."""
    
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    document_url = serializers.SerializerMethodField()
    
    class Meta:
        model = UserDocument
        fields = [
            'id', 'document_type', 'document_type_display', 'document_url',
            'document_number', 'status', 'status_display', 'rejection_reason',
            'uploaded_at', 'verified_at'
        ]
        read_only_fields = ['id', 'status', 'rejection_reason', 'uploaded_at', 'verified_at']

    def get_document_url(self, obj):
        request = self.context.get('request')
        if request:
            from .document_service import resolve_document_url

            return resolve_document_url(request, obj.document_url)
        return obj.document_url


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for user lists."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile_image = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'profile_image', 'role', 'average_rating', 'total_reviews',
            'is_verified_tasker', 'is_online'
        ]
        read_only_fields = fields

    def get_profile_image(self, obj):
        """Return full URL for profile image (same as UserDetailSerializer)."""
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None


class PublicUserSerializer(serializers.ModelSerializer):
    """
    Public-safe user serializer (no email/phone).
    Use for any AllowAny endpoints (reviews, public listings, etc.).
    """

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'full_name',
            'profile_image',
            'average_rating',
            'total_reviews',
            'is_verified_tasker',
            'is_online',
        ]
        read_only_fields = fields

    def get_profile_image(self, obj):
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for user profiles."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    full_address = serializers.CharField(read_only=True)
    skills = UserSkillSerializer(many=True, read_only=True)
    badges = UserBadgeSerializer(many=True, read_only=True)
    profile_image = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    username_can_change = serializers.SerializerMethodField()
    username_next_change_at = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'username_changed_at', 'username_can_change',
            'username_next_change_at', 'first_name', 'last_name', 'full_name',
            'phone', 'date_of_birth', 'gender', 'bio', 'tagline',
            'profile_image', 'cover_image', 'role',
            'email_verified', 'phone_verified', 'identity_verified', 'is_verified_tasker', 'has_payment_method',
            'address', 'city', 'state', 'country', 'postal_code', 'full_address',
            'latitude', 'longitude',
            'average_rating', 'total_reviews', 'tasks_completed', 'tasks_posted',
            'hourly_rate', 'response_time', 'completion_rate',
            'is_online', 'last_seen',
            'notification_enabled', 'email_notifications', 'sms_notifications', 'push_notifications',
            'date_joined', 'skills', 'badges'
        ]
        read_only_fields = [
            'id', 'email_verified', 'phone_verified', 'identity_verified',
            'is_verified_tasker', 'has_payment_method', 'average_rating', 'total_reviews',
            'tasks_completed', 'tasks_posted', 'response_time', 'completion_rate',
            'is_online', 'last_seen', 'date_joined', 'username_changed_at',
            'username_can_change', 'username_next_change_at',
        ]

    def get_username_can_change(self, obj):
        from .username_policy import get_username_change_status

        can_change, _ = get_username_change_status(obj)
        return can_change

    def get_username_next_change_at(self, obj):
        from .username_policy import get_username_change_status

        _, next_at = get_username_change_status(obj)
        return next_at.isoformat() if next_at else None
    
    def get_profile_image(self, obj):
        """Return full URL for profile image."""
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None
    
    def get_cover_image(self, obj):
        """Return full URL for cover image."""
        if obj.cover_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.cover_image.url)
            return obj.cover_image.url
        return None


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    USERNAME_PATTERN = r'^[a-z0-9._]+$'
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'username', 'phone', 'date_of_birth', 'gender',
            'bio', 'tagline', 'profile_image', 'cover_image',
            'address', 'city', 'state', 'country', 'postal_code',
            'latitude', 'longitude', 'hourly_rate',
            'notification_enabled', 'email_notifications', 'sms_notifications', 'push_notifications'
        ]
    
    def validate_phone(self, value):
        """Validate phone number format."""
        if value and not value.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise serializers.ValidationError("Invalid phone number format.")
        return value

    def validate_username(self, value):
        import re

        from .username_policy import assert_username_change_allowed, normalize_username

        if value is None or value == '':
            raise serializers.ValidationError('Username is required.')

        normalized = normalize_username(value)
        if len(normalized) < 3:
            raise serializers.ValidationError('Username must be at least 3 characters.')
        if len(normalized) > 150:
            raise serializers.ValidationError('Username must not exceed 150 characters.')
        if not re.match(self.USERNAME_PATTERN, normalized):
            raise serializers.ValidationError(
                'Username can only contain letters, numbers, dots, and underscores.'
            )

        user = self.instance
        if user:
            assert_username_change_allowed(user, normalized)

        return normalized

    def update(self, instance, validated_data):
        from django.utils import timezone

        from .username_policy import normalize_username, usernames_equal

        new_username = validated_data.get('username')
        if new_username is not None:
            if not usernames_equal(instance.username, new_username):
                validated_data['username'] = normalize_username(new_username)
                validated_data['username_changed_at'] = timezone.now()

        return super().update(instance, validated_data)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone', 'role'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def validate_email(self, value):
        """
        Ensure uniqueness using the same normalization as UserManager.create_user().

        Without this, DRF's default UniqueValidator can pass for case-variants,
        but create_user() normalizes and can still hit the DB UNIQUE constraint.
        """
        normalized = BaseUserManager.normalize_email((value or '').strip())
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized
    
    def validate_role(self, value):
        """Validate role selection."""
        if value not in ['customer', 'tasker']:
            raise serializers.ValidationError("Invalid role. Must be 'customer' or 'tasker'.")
        return value
    
    def create(self, validated_data):
        """Create new user."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs
    
    def validate_old_password(self, value):
        """Validate old password."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request."""
    
    email = serializers.EmailField(required=True)
    # Intentionally do NOT validate existence to avoid leaking which emails
    # are registered (account enumeration). The view will send email only
    # when a matching user exists.


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation."""
    
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification."""
    
    token = serializers.CharField(required=True)


class UserStatsSerializer(serializers.ModelSerializer):
    """Serializer for user statistics."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'profile_image', 'role',
            'average_rating', 'total_reviews', 'tasks_completed', 'tasks_posted',
            'completion_rate', 'response_time', 'total_earned', 'total_spent',
            'wallet_balance', 'date_joined'
        ]
        read_only_fields = fields


class TaskerPublicProfileSerializer(serializers.ModelSerializer):
    """Public profile serializer for taskers (visible to customers)."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile_image = serializers.SerializerMethodField()
    skills = UserSkillSerializer(many=True, read_only=True)
    badges = UserBadgeSerializer(many=True, read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'username', 'profile_image', 'cover_image',
            'bio', 'tagline', 'city', 'state', 'country',
            'average_rating', 'total_reviews', 'tasks_completed',
            'hourly_rate', 'response_time', 'completion_rate',
            'is_verified_tasker', 'is_online', 'last_seen',
            'skills', 'badges', 'date_joined'
        ]
        read_only_fields = fields

    def get_profile_image(self, obj):
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None


class PublicProfileSerializer(TaskerPublicProfileSerializer):
    """Public profile for /users/[username] — customers and taskers."""

    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    display_name = serializers.SerializerMethodField()
    location_display = serializers.SerializerMethodField()
    online_status = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    transportation_tags = serializers.SerializerMethodField()
    badges = serializers.SerializerMethodField()

    class Meta(TaskerPublicProfileSerializer.Meta):
        fields = TaskerPublicProfileSerializer.Meta.fields + [
            'first_name', 'last_name', 'display_name', 'location_display',
            'online_status', 'followers_count', 'following_count', 'is_following',
            'transportation_tags', 'tasks_posted', 'role',
        ]

    def get_display_name(self, obj):
        first = (obj.first_name or '').strip()
        last = (obj.last_name or '').strip()
        if first and last:
            return f"{first} {last[0]}."
        return obj.get_full_name() or obj.username or 'User'

    def get_location_display(self, obj):
        parts = [p for p in [obj.city, obj.state, obj.country] if p]
        if parts:
            return ', '.join(parts)
        return obj.address or ''

    def get_online_status(self, obj):
        if obj.is_online:
            return 'Online now'
        if obj.last_seen:
            from django.utils import timezone
            delta = timezone.now() - obj.last_seen
            if delta.days < 1:
                return 'Online less than a day ago'
            if delta.days == 1:
                return 'Online 1 day ago'
            return f'Online {delta.days} days ago'
        return 'Offline'

    is_following = serializers.SerializerMethodField()

    def get_followers_count(self, obj):
        return obj.user_followers.count()

    def get_following_count(self, obj):
        return obj.user_following.count()

    def get_is_following(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.user_followers.filter(follower=request.user).exists()

    def get_transportation_tags(self, obj):
        tags = []
        skills = obj.skills.all() if hasattr(obj, 'skills') else []
        for skill in skills:
            category = (getattr(skill, 'category', '') or '').strip().lower()
            if category != 'transport':
                continue
            name = (getattr(skill, 'name', '') or '').strip()
            if name:
                tags.append(name)
        if not tags and getattr(obj, 'role', None) == 'tasker':
            return ['Online']
        return tags

    def get_badges(self, obj):
        verified = obj.badges.filter(is_verified=True).order_by('-verified_at', '-earned_at')
        return PublicUserBadgeSerializer(
            verified,
            many=True,
            context=self.context,
        ).data


class PortfolioItemSerializer(serializers.ModelSerializer):
    """Serializer for portfolio items."""

    file = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    rejection_reason = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioItem
        fields = [
            'id', 'title', 'description', 'file', 'file_type',
            'file_size', 'order', 'status', 'status_display',
            'rejection_reason', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'file', 'file_type', 'file_size', 'status',
            'status_display', 'rejection_reason', 'created_at', 'updated_at',
        ]

    def _portfolio_document(self, obj):
        cached = getattr(obj, '_portfolio_document', None)
        if cached is not None:
            return cached
        from .portfolio_service import portfolio_document_status_map

        doc_map = self.context.get('portfolio_doc_map')
        if doc_map is None:
            doc_map = portfolio_document_status_map(obj.user)
        doc = doc_map.get(str(obj.id))
        obj._portfolio_document = doc
        return doc

    def get_file(self, obj):
        request = self.context.get('request')
        stored = obj.file
        if not stored:
            return stored
        if request:
            from .portfolio_service import resolve_portfolio_file_url

            return resolve_portfolio_file_url(request, stored)
        return stored

    def get_status(self, obj):
        doc = self._portfolio_document(obj)
        return doc.status if doc else 'pending'

    def get_status_display(self, obj):
        doc = self._portfolio_document(obj)
        return doc.get_status_display() if doc else 'Pending'

    def get_rejection_reason(self, obj):
        doc = self._portfolio_document(obj)
        if doc and doc.status == 'rejected':
            return doc.rejection_reason
        return ''
