"""Dedicated marketplace jobs API (Task rows with listing:job tag)."""

from django.db.models import Q

from django.utils import timezone

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, status, viewsets

from rest_framework.decorators import action

from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

from rest_framework.response import Response



from apps.tasks.models import TaskQuestion

from apps.tasks.permissions import IsTaskOwner
from apps.tasks.question_utils import block_owner_asking_question
from apps.tasks.serializers import TaskQuestionSerializer

from apps.bookmark.mixins import BookmarkSerializerContextMixin

from .models import Job

from .permissions import CanCreateJob

from .serializers import (

    JobCreateSerializer,

    JobDetailSerializer,

    JobListSerializer,

    JobUpdateSerializer,

)





class JobViewSet(BookmarkSerializerContextMixin, viewsets.ModelViewSet):

    """

    Marketplace jobs API.



    GET  /api/v1/jobs/           — public open jobs

    GET  /api/v1/jobs/{slug}/    — job detail

    POST /api/v1/jobs/           — create (employers)

    PATCH /api/v1/jobs/{slug}/   — update (owner)

    DELETE /api/v1/jobs/{slug}/  — delete (owner)

    GET  /api/v1/jobs/mine/      — current user's jobs

    """



    permission_classes = [IsAuthenticatedOrReadOnly]

    lookup_field = 'slug'

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    search_fields = ['title', 'description', 'city', 'tags']

    ordering_fields = ['created_at', 'budget_amount', 'bids_count']

    filterset_fields = ['status', 'category', 'work_type', 'location_type', 'city', 'country']



    def get_queryset(self):

        user = self.request.user

        queryset = Job.objects.all()



        if user.is_authenticated:

            queryset = queryset.filter(Q(is_public=True) | Q(owner=user))

        else:

            queryset = queryset.filter(is_public=True, status='open')



        return queryset.select_related(
            'owner',
            'owner__employer_profile',
            'category',
            'assigned_tasker',
        ).prefetch_related('attachments', 'questions', 'questions__asked_by')



    def filter_queryset(self, queryset):

        queryset = super().filter_queryset(queryset)

        if self.action == 'list' and not self.request.user.is_authenticated:

            queryset = queryset.filter(is_public=True, status='open')

        return queryset



    def get_serializer_class(self):

        if self.action == 'list' or self.action == 'mine':

            return JobListSerializer

        if self.action == 'retrieve':

            return JobDetailSerializer

        if self.action == 'create':

            return JobCreateSerializer

        if self.action in ('update', 'partial_update'):

            return JobUpdateSerializer

        return JobDetailSerializer



    def get_permissions(self):

        if self.action == 'create':

            return [IsAuthenticated(), CanCreateJob()]

        if self.action in ('update', 'partial_update', 'destroy'):

            return [IsAuthenticated(), IsTaskOwner()]

        if self.action == 'mine':

            return [IsAuthenticated()]

        return super().get_permissions()



    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        task = serializer.save()

        output = JobDetailSerializer(task, context={'request': request})

        return Response(output.data, status=status.HTTP_201_CREATED)



    def update(self, request, *args, **kwargs):

        partial = kwargs.pop('partial', False)

        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        serializer.is_valid(raise_exception=True)

        task = serializer.save()

        output = JobDetailSerializer(task, context={'request': request})

        return Response(output.data)



    def partial_update(self, request, *args, **kwargs):

        kwargs['partial'] = True

        return self.update(request, *args, **kwargs)



    @action(detail=False, methods=['get'], url_path='mine')

    def mine(self, request):

        """Dashboard: jobs owned by the authenticated employer."""

        queryset = (

            Job.objects.filter(owner=request.user)

            .select_related('owner', 'owner__employer_profile', 'category')

            .prefetch_related('attachments')

            .order_by('-created_at')

        )

        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)

        if page is not None:

            serializer = JobListSerializer(page, many=True, context={'request': request})

            return self.get_paginated_response(serializer.data)

        serializer = JobListSerializer(queryset, many=True, context={'request': request})

        return Response(serializer.data)



    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])

    def ask_question(self, request, slug=None):

        """Ask a question about the job."""

        job = self.get_object()

        blocked = block_owner_asking_question(job, request.user)
        if blocked is not None:
            return blocked

        serializer = TaskQuestionSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        question = serializer.save(task=job, asked_by=request.user)

        output = TaskQuestionSerializer(question, context={'request': request})

        return Response(output.data, status=status.HTTP_201_CREATED)



    @action(

        detail=True,

        methods=['patch'],

        url_path=r'questions/(?P<question_id>[0-9a-f-]{36})',

        permission_classes=[IsAuthenticated, IsTaskOwner],

    )

    def answer_question(self, request, slug=None, question_id=None):

        """Post or update an answer (job owner only)."""

        job = self.get_object()



        try:

            question = job.questions.get(pk=question_id)

        except TaskQuestion.DoesNotExist:

            return Response(

                {'detail': 'Question not found.'},

                status=status.HTTP_404_NOT_FOUND,

            )



        answer = (request.data.get('answer') or '').strip()

        if not answer:

            return Response(

                {'answer': ['Answer cannot be empty.']},

                status=status.HTTP_400_BAD_REQUEST,

            )



        question.answer = answer

        question.answered_at = timezone.now()

        question.save(update_fields=['answer', 'answered_at'])



        serializer = TaskQuestionSerializer(question, context={'request': request})

        return Response(serializer.data)

