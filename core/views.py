# core/views.py 頂部
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse # JsonResponse 也放到這裡
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone # 為了 WeakTopic 的 last_diagnosed
from .repositories import UserRepository, WrongQuestionRepository, WeakTopicRepository, TestRecordRepository 


from django.db.models import Min, Count, Q 
from collections import OrderedDict

from dotenv import load_dotenv
import json
import random
import os

# 統一從 .models 導入所有需要的模型
from .models import User, Question, Favorite, TestRecord, WrongQuestion, Explanation, GptLog, Feedback, WeakTopic

# 導入 services (避免重複導入)
from .services.gpt_service import GPTExplanationService
from .services.openai_client import OpenAIClient
from .services.auth_service import AuthService

# ⬇ 實例化 Repositories (放在檔案頂部，大家共用) ⬇
user_repo = UserRepository()
wrong_question_repo = WrongQuestionRepository()
weak_topic_repo = WeakTopicRepository()
test_record_repo = TestRecordRepository()


load_dotenv()  # 讀取 .env 檔案

auth_service = AuthService()

def home(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('core:login')

    explanation = None
    if request.method == 'POST':
        question = request.POST.get('question')
        answer = request.POST.get('answer')

        import os
        client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
        service = GPTExplanationService(gpt_client=client)
        explanation = service.explain(question, answer)

    return render(request, 'home.html', {'explanation': explanation})


def login_view(request):
    user_id = request.session.get('user_id')
    if user_id:
        return redirect('core:dashboard') 

    message = ""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        success, message = auth_service.login(request, username, password)
        if success:
            return redirect('core:dashboard')  # 登入成功導向主頁
    return render(request, 'login.html', {'message': message})


def logout_view(request):
    auth_service.logout(request)
    return redirect('core:login')  # 登出後導回首頁登入


def dashboard_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('core:login')

    return render(request, 'dashboard.html')


def start_test_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('core:login')

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

        return redirect('core:test_question', question_index=0)

    return render(request, 'start_test.html')


def test_question_view(request, question_index):
    config = request.session.get('test_config')
    if not config:
        return redirect('core:start_test')

    if 'test_questions' not in request.session:
        topic = config['topic']
        count = config['count']
        all_questions = list(Question.objects.filter(topic=topic))
        selected = random.sample(all_questions, min(count, len(all_questions)))
        request.session['test_questions'] = [q.id for q in selected]
        request.session['answers'] = {}

    question_ids = request.session['test_questions']
    if question_index >= len(question_ids):
        return redirect('core:dashboard')

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
        return redirect('core:login')

    test_result_id = request.session.get('test_result_id')
    if not test_result_id:
        return redirect('core:start_test')

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



def register_view(request):
    message = ""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        success, message = auth_service.register(username, password)
        if success:
            return redirect('core:login')  # 註冊成功就跳回登入頁
    return render(request, 'register.html', {'message': message})


def logout_view(request):
    auth_service.logout(request)
    return redirect('core:login')


def user_management_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('core:login')

    current_user = User.objects.get(id=user_id)
    if current_user.role != 'admin':
        return HttpResponseForbidden("你沒有權限瀏覽此頁面")

    if request.method == 'POST':
        target_id = request.POST.get('user_id')
        new_role = request.POST.get('role')

        if str(current_user.id) == target_id:
            messages.error(request, "無法修改自己的權限。")
            return redirect('core:user_management')

        target_user = User.objects.get(id=target_id)
        target_user.role = new_role
        target_user.save()
        messages.success(request, f"使用者 {target_user.username} 已更新為 {new_role}。")
        return redirect('core:user_management')

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


def wrong_questions_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('core:login')

    current_user_instance = user_repo.get_user_by_id(user_id) # <--- 使用 UserRepository
    if not current_user_instance:
        request.session.pop('user_id', None) 
        return redirect('core:login')

    selected_topic = request.GET.get('topic', None)

    # 使用 WrongQuestionRepository 的方法來獲取錯題列表
    wrong_list = wrong_question_repo.get_unconfirmed_by_user_and_topic(
        user=current_user_instance, 
        topic=selected_topic
    )

    # 使用 WrongQuestionRepository 的方法來獲取可用主題
    available_topics = wrong_question_repo.get_distinct_topics_for_unconfirmed_by_user(
        user=current_user_instance
    )

    context = {
        'wrong_questions': wrong_list,
        'available_topics': available_topics,
        'current_topic': selected_topic if selected_topic else 'all'
    }
    return render(request, 'wrong_questions.html', context)
    

def diagnose_weakness_view(request):
    user_id = request.session.get('user_id')
    if not user_id: # 確保檢查 user_id 是否存在
        return redirect('core:login')

    current_user = user_repo.get_user_by_id(user_id) # <--- 1. 使用 UserRepository
    if not current_user:
        request.session.pop('user_id', None)
        return redirect('core:login')

    analysis_result = {
        "weak_topics": [], 
        "summary": "點擊「開始進行弱點分析」按鈕來查看您的 AI 診斷報告。"
    }
    
    if request.method == 'POST':
        # 2. 使用 WrongQuestionRepository 獲取錯題樣本
        #    sample_count 的邏輯可以封裝在 Repository 方法內部，或者在這裡計算好再傳入
        all_user_wrong_questions_count = wrong_question_repo.get_unconfirmed_by_user_and_topic(user=current_user).count()
        sample_count = all_user_wrong_questions_count // 2
        if sample_count == 0 and all_user_wrong_questions_count > 0:
            sample_count = 1
        # (可以進一步調整 sample_count 的邏輯，例如設定最小取樣數)
            
        wrong_questions_for_analysis = wrong_question_repo.get_sample_for_weakness_analysis(current_user, sample_count) # <--- 2. 使用 Repository 方法

        if wrong_questions_for_analysis:
            data_for_gpt = []
            for wq_object in wrong_questions_for_analysis: # wq_object 現在是 WrongQuestion 的實例
                data_for_gpt.append({
                    'question_obj': wq_object.question, # 假設 get_sample_for_weakness_analysis 回傳的是 WrongQuestion 實例列表
                })

            if os.getenv("OPENAI_API_KEY"):
                client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
                # 假設 GPTExplanationService 已經在檔案頂部被實例化為 gpt_service
                # 如果不是，需要在这里實例化 gpt_service = GPTExplanationService(gpt_client=client)
                # 目前的寫法是在頂部有 auth_service = AuthService()，但 gpt_service 可能需要在函式內或頂部實例化
                # 為了與現有 gpt_detail_view 邏輯一致，我們在需要時才實例化
                gpt_service = GPTExplanationService(gpt_client=client) 
                
                predefined_topics = None 
                current_analysis_from_service = gpt_service.analyze_weaknesses(data_for_gpt, predefined_weak_topics=predefined_topics)
                print(f"Analysis Result from Service: {current_analysis_from_service}") 
                
                analysis_result["summary"] = current_analysis_from_service.get("summary", "AI分析未能提供有效的文字摘要。")
                analysis_result["weak_topics"] = current_analysis_from_service.get("weak_topics", [])

                if analysis_result["weak_topics"]:
                    for topic_name in analysis_result["weak_topics"]:
                        if topic_name: 
                            # 3. 使用 WeakTopicRepository 儲存弱點主題
                            weak_topic_repo.update_or_create_weak_topic(current_user, topic_name) # <--- 3. 使用 Repository 方法
                    print(f"Saved/Updated WeakTopics for user {current_user.username}")
            else:
                analysis_result["summary"] = "OpenAI API 金鑰未設定，無法進行 AI 分析。"
        else:
            analysis_result["summary"] = "沒有足夠的錯題進行分析（目前選取0題）。"
    
    # 4. 使用 WeakTopicRepository 獲取已記錄的弱點主題
    existing_weak_topics = weak_topic_repo.get_weak_topics_for_user(current_user) # <--- 4. 使用 Repository 方法
    print(f"Existing Weak Topics from DB for user {current_user.username}: {list(existing_weak_topics.values_list('topic', flat=True))}")

    context = {
        'analysis_summary': analysis_result.get("summary"),
        'existing_weak_topics': existing_weak_topics, 
        'page_title': "AI 弱點診斷"
    }
    # 確保模板名稱是實際的檔案名，之前確認是 'weakness_analysis_result.html'
    return render(request, 'weakness_analysis_result.html', context) 


def grade_history_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('core:login')

    current_user = user_repo.get_user_by_id(user_id)
    if not current_user:
        request.session.pop('user_id', None)
        return redirect('core:login')

    # 透過 Repository 獲取測驗歷史摘要
    test_history_details = test_record_repo.get_recent_test_session_summaries(user=current_user, limit=10)

    context = {
        'test_history': test_history_details,
        'page_title': "測驗歷史記錄"
    }
    return render(request, 'grade_history.html', context)