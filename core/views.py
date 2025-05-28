from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .services.gpt_service import GPTExplanationService
from .services.openai_client import OpenAIClient
from .services.auth_service import AuthService
from .models import User, Favorite, Question, TestRecord
from dotenv import load_dotenv
import json
import random
import os


load_dotenv()  # 讀取 .env 檔案

auth_service = AuthService()

def home(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    explanation = None
    if request.method == 'POST':
        question = request.POST.get('question')
        answer = request.POST.get('answer')

        import os
        client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
        service = GPTExplanationService(gpt_client=client)
        explanation = service.explain(question, answer)

    return render(request, 'home.html', {'explanation': explanation})


def register_view(request):
    message = ""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        success, message = auth_service.register(username, password)
        if success:
            return redirect('login')  # 註冊成功就跳回登入頁
    return render(request, 'register.html', {'message': message})


def login_view(request):
    user_id = request.session.get('user_id')
    if user_id:
        return redirect('dashboard') 

    message = ""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        success, message = auth_service.login(request, username, password)
        if success:
            return redirect('dashboard')  # 登入成功導向主頁
    return render(request, 'login.html', {'message': message})


def logout_view(request):
    auth_service.logout(request)
    return redirect('login')  # 登出後導回首頁登入


def dashboard_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    return render(request, 'dashboard.html')


def start_test_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    if request.method == 'POST':
        # 清除舊的測驗紀錄，避免影響正確率與錯題計算
        request.session.pop('test_questions', None)
        request.session.pop('answers', None)

        import uuid
        test_result_id = str(uuid.uuid4())
        request.session['test_result_id'] = test_result_id

        topic = request.POST.get("topic")
        count = int(request.POST.get("count"))
        mode = request.POST.get("mode")
        include_gpt = request.POST.get("include_gpt")  # 'yes' or 'no'

        request.session['test_config'] = {
            'topic': topic,
            'count': count,
            'mode': mode,
            'include_gpt': include_gpt
        }

        # 題庫篩選
        qs = Question.objects.filter(topic=topic)
        if include_gpt == 'no':
            qs = qs.filter(is_gpt_generated=False)

        # 隨機選題
        selected = random.sample(list(qs), min(count, qs.count()))

        # 存進 session
        request.session['test_questions'] = [q.id for q in selected]
        request.session['answers'] = {}

        return redirect('test_question', question_index=0)

    return render(request, 'start_test.html')


def test_question_view(request, question_index):
    config = request.session.get('test_config')
    if not config:
        return redirect('start_test')

    if 'test_questions' not in request.session:
        topic = config['topic']
        count = config['count']
        all_questions = list(Question.objects.filter(topic=topic))
        selected = random.sample(all_questions, min(count, len(all_questions)))
        request.session['test_questions'] = [q.id for q in selected]
        request.session['answers'] = {}

    question_ids = request.session['test_questions']
    if question_index >= len(question_ids):
        return redirect('dashboard')

    selected_answer = None
    if request.method == 'POST':
        selected_answer = request.POST.get('answer')
        question = Question.objects.get(id=question_ids[question_index])
        answers = request.session.get('answers', {})
        answers[str(question.id)] = selected_answer
        request.session['answers'] = answers

        user_id = request.session.get('user_id')
        test_result_id = request.session.get('test_result_id')

        print("user_id:", user_id)
        print("test_result_id:", test_result_id)
        print("selected:", selected_answer)

        if user_id and test_result_id:
            TestRecord.save_answer(user_id, question, selected_answer, test_result_id)


    else:
        question = Question.objects.get(id=question_ids[question_index])

    return render(request, 'test_question.html', {
        'question': question,
        'index': question_index,
        'total': len(question_ids),
        'selected': selected_answer
    })


def test_result_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    test_result_id = request.session.get('test_result_id')
    if not test_result_id:
        return redirect('start_test')

    records = TestRecord.objects.filter(user_id=user_id, test_result_id=test_result_id)

    total = records.count()
    correct_count = records.filter(is_correct=True).count()
    accuracy = round((correct_count / total) * 100, 2) if total else 0
    wrong_records = records.filter(is_correct=False)


    # 排序：依照這次測驗的 test_questions 順序
    question_order = request.session.get('test_questions', [])

    # 加上 index 編號（0-based 改成 1-based）
    indexed_wrong_records = []
    for record in wrong_records:
        try:
            seq = question_order.index(record.question.id) + 1
        except ValueError:
            seq = "?"
        indexed_wrong_records.append({
            'record': record,
            'seq': seq
        })


    # 清掉本輪測驗的 ID，避免誤用
    request.session.pop('test_result_id', None)

    return render(request, 'test_result.html', {
        'correct_count': correct_count,
        'total': total,
        'accuracy': accuracy,
        'wrong_records': indexed_wrong_records
    })


def gpt_detail_view(request):
    user_id = request.session.get('user_id')
    qid = int(request.GET.get('qid'))
    question = Question.objects.get(id=qid)

    # 查詢是否已收藏
    is_starred = Favorite.objects.filter(user_id=user_id, question=question).exists()

    # 找下一題編號（如果有）
    test_questions = request.session.get('test_questions', [])
    next_index = None
    if qid in test_questions:
        index = test_questions.index(qid)
        if index + 1 < len(test_questions):
            next_index = index + 1

    # 取得回答記錄
    answers = request.session.get('answers', {})
    selected = answers.get(str(qid))

    # GPT 解釋
    client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
    service = GPTExplanationService(gpt_client=client)
    explanation = service.explain(
        question.content,
        question.answer,
        question.options
    )

    return render(request, 'gpt_detail.html', {
        'question': question,
        'selected': selected,
        'explanation': explanation,
        'is_starred': is_starred,
        'next_index': next_index,
    })



def logout_view(request):
    auth_service.logout(request)
    return redirect('login')


def user_management_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    current_user = User.objects.get(id=user_id)
    if current_user.role != 'admin':
        return HttpResponseForbidden("你沒有權限瀏覽此頁面")

    if request.method == 'POST':
        target_id = request.POST.get('user_id')
        new_role = request.POST.get('role')

        if str(current_user.id) == target_id:
            messages.error(request, "無法修改自己的權限。")
            return redirect('user_management')

        target_user = User.objects.get(id=target_id)
        target_user.role = new_role
        target_user.save()
        messages.success(request, f"使用者 {target_user.username} 已更新為 {new_role}。")
        return redirect('user_management')

    users = User.objects.all()
    return render(request, 'user_management.html', {'users': users})


@csrf_exempt
def save_answer_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        qid = str(data.get('qid'))
        ans = data.get('answer')

        user_id = request.session.get('user_id')
        test_result_id = request.session.get('test_result_id')
        if user_id and test_result_id:
            question = Question.objects.get(id=qid)
            TestRecord.save_answer(user_id, question, ans, test_result_id)

        answers = request.session.get('answers', {})
        answers[qid] = ans
        request.session['answers'] = answers

        return JsonResponse({'status': 'ok'})


    return JsonResponse({'error': 'invalid request'}, status=400)


@csrf_exempt
def toggle_star_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = request.session.get('user_id')
            qid = data.get('qid')
            question = Question.objects.get(id=qid)

            favorite, created = Favorite.objects.get_or_create(
                user_id=user_id,
                question=question
            )

            if not created:
                favorite.delete()
                return JsonResponse({'starred': False})
            else:
                return JsonResponse({'starred': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'invalid method'}, status=405)
    

@login_required
def update_note_view(request, fav_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        note_text = request.POST.get('note', '')
        Favorite.update_note(fav_id, user_id, note_text)  # 封裝在 model 內
        return redirect('wrong_questions')


@login_required
def wrong_questions_view(request):
    user_id = request.session.get('user_id')
    favorites = Favorite.get_user_favorites(user_id)  # 呼叫封裝好的方法
    return render(request, 'wrong_questions.html', {'favorites': favorites})

