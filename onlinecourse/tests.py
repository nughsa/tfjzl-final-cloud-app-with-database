from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Course, Enrollment, Question, Choice, Submission


class AssessmentFeatureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='learner1',
            email='learner1@example.com',
            password='secret123',
            first_name='Learner',
            last_name='One',
        )
        self.course = Course.objects.create(
            name='Python Basics',
            description='Learn the basics of Python.',
            pub_date='2024-01-01',
            image=SimpleUploadedFile('course.png', b'content', content_type='image/png'),
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            mode='honor',
        )
        self.question = Question.objects.create(
            course=self.course,
            text='What is 2 + 2?',
            grade=10,
        )
        self.choice_correct = Choice.objects.create(
            question=self.question,
            choice_text='4',
            is_correct=True,
        )
        self.choice_wrong = Choice.objects.create(
            question=self.question,
            choice_text='5',
            is_correct=False,
        )

    def test_course_detail_renders_exam_form_for_enrolled_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('onlinecourse:course_details', args=[self.course.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What is 2 + 2?')
        self.assertContains(response, 'Submit Exam')

    def test_submit_exam_creates_submission_and_redirects_to_results(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('onlinecourse:submit_exam', args=[self.course.id]),
            {'choice_%s' % self.choice_correct.id: str(self.choice_correct.id)},
        )
        self.assertEqual(response.status_code, 302)
        submission = Submission.objects.get(enrollment=self.enrollment)
        self.assertIn(self.choice_correct, submission.choices.all())
