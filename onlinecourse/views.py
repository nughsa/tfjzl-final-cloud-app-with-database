from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
# <HINT> Import any new Models here
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.is_authenticated and user.id is not None:
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        user = self.request.user
        context['is_enrolled'] = check_if_enrolled(user, course)
        if context['is_enrolled']:
            context['questions'] = course.questions.all().order_by('id')
        return context


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))


@login_required
def submit_exam(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    enrollment = get_object_or_404(Enrollment, user=request.user, course=course)

    submission = Submission.objects.create(enrollment=enrollment)
    selected_choice_ids = extract_answers(request)
    selected_choices = Choice.objects.filter(id__in=selected_choice_ids, question__course=course)
    submission.choices.add(*selected_choices)
    submission.score = calculate_score(course, submission)
    submission.save()

    return redirect('onlinecourse:show_exam_result', course_id=course.id, submission_id=submission.id)


# An example method to collect the selected choices from the exam form from the request object
def extract_answers(request):
    submitted_answers = []
    for key in request.POST:
        if key.startswith('choice'):
            value = request.POST[key]
            try:
                choice_id = int(value)
                submitted_answers.append(choice_id)
            except ValueError:
                continue
    return submitted_answers


def calculate_score(course, submission):
    selected_choice_ids = set(submission.choices.values_list('id', flat=True))
    total_score = 0
    for question in course.questions.all():
        correct_choice_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
        selected_for_question = set(question.choices.filter(id__in=selected_choice_ids).values_list('id', flat=True))
        if selected_for_question == correct_choice_ids and correct_choice_ids:
            total_score += question.grade
    return total_score


def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)
    selected_choice_ids = set(submission.choices.values_list('id', flat=True))
    total_possible = 0
    total_score = 0
    question_results = []

    for question in course.questions.all().order_by('id'):
        total_possible += question.grade
        selected_for_question = question.choices.filter(id__in=selected_choice_ids)
        correct_choice_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
        selected_ids = set(selected_for_question.values_list('id', flat=True))
        is_correct = (selected_ids == correct_choice_ids) and bool(correct_choice_ids)
        earned_points = question.grade if is_correct else 0
        total_score += earned_points
        question_results.append({
            'question': question,
            'question_text': question.text,
            'question_grade': question.grade,
            'selected_choices': selected_for_question,
            'is_correct': is_correct,
            'points': earned_points,
        })

    if total_possible > 0:
        grade = round((total_score / total_possible) * 100, 2)
    else:
        grade = 0

    submission.score = total_score
    submission.save()

    return render(request, 'onlinecourse/exam_result_bootstrap.html', {
        'course': course,
        'submission': submission,
        'grade': grade,
        'total_score': total_score,
        'total_possible': total_possible,
        'question_results': question_results,
    })


# <HINT> Create an exam result view to check if learner passed exam and show their question results and result for each question,
# you may implement it based on the following logic:
        # Get course and submission based on their ids
        # Get the selected choice ids from the submission record
        # For each selected choice, check if it is a correct answer or not
        # Calculate the total score
#def show_exam_result(request, course_id, submission_id):



