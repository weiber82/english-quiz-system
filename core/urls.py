from django.urls import path
from django.contrib import admin
from . import views
from .views import test_result_view

app_name = 'core' # 建議加上，為 URL 設定命名空間

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('admin/users/', views.user_management_view, name='user_management'),
    path('start-test/', views.start_test_view, name='start_test'),
    path('test/<int:question_index>/', views.test_question_view, name='test_question'),
    path('test/result/', test_result_view, name='test_result'),
    path('api/save-answer/', views.save_answer_view, name='save_answer'),
    path('gpt/', views.gpt_detail_view, name='gpt_detail'),
    path('gpt/manual/', views.home, name='gpt_manual'),
    path('api/toggle-star/', views.toggle_star_view, name='toggle_star'),
    path('diagnose-weakness/', views.diagnose_weakness_view, name='diagnose_weakness'),
    path('grade-history/', views.grade_history_view, name='grade_history'),
    
    # ⬇ 新增的錯題本路徑 ⬇
    path('my-mistakes/', views.wrong_questions_view, name='my_wrong_questions'),
]
