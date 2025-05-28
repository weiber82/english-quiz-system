from django.db import models
from django.utils import timezone



class User(models.Model):
    ROLE_CHOICES = (
        ('student', '學生'),
        ('admin', '管理員'),
    )

    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')

    def __str__(self):
        return f"{self.username} ({self.role})"


    @classmethod
    def find_by_username(cls, username):
        try:
            return cls.objects.get(username=username)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create(cls, username, password):
        return cls.objects.create(username=username, password=password)


class Question(models.Model):
    content = models.TextField()
    options = models.JSONField()  # 用 dict 儲存 ABCD
    answer = models.CharField(max_length=1)  # 正解 A/B/C/D
    topic = models.CharField(max_length=50)  # vocab/grammar/cloze/reading
    is_gpt_generated = models.BooleanField(default=False)
    created_dt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content[:30]
    

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    note = models.TextField(blank=True)  # 📝 可加筆記（選填）
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question')  # 每人每題只能收藏一次


class TestRecord(models.Model):
    test_result_id = models.CharField(max_length=64) 

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1)
    is_correct = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Q{self.question.id} - Ans: {self.selected_option}"

    @classmethod
    def save_answer(cls, user_id, question, selected_option, test_result_id):
        # --- 在方法內部導入和實例化 Repositories ---
        from .repositories import UserRepository, WrongQuestionRepository # <--- 改到這裡導入
        user_repo = UserRepository()
        wrong_question_repo = WrongQuestionRepository()
        # --- 導入和實例化結束 ---

        if not cls.has_answered(user_id, question.id, test_result_id):
            is_correct_val = (selected_option == question.answer)

            user_instance_for_logic = user_repo.get_user_by_id(user_id) # 使用方法內實例化的 repo

            if not user_instance_for_logic:
                print(f"ERROR: User with id {user_id} not found in TestRecord.save_answer") # 加上 log
                return 

            cls.objects.create( 
                user=user_instance_for_logic, 
                question=question,
                selected_option=selected_option,
                is_correct=is_correct_val, 
                test_result_id=test_result_id
            )

            if not is_correct_val:
                wq, created = wrong_question_repo.get_or_create( # 使用方法內實例化的 repo
                    user=user_instance_for_logic,
                    question=question,
                    defaults={'confirmed': False, 'note': ''}
                )

                if not created:
                    wq.confirmed = False
                    wrong_question_repo.update_wrong_question_fields(wq, fields_to_update=['confirmed'])


    @classmethod
    def has_answered(cls, user_id, question_id, test_result_id):
        return cls.objects.filter(user_id=user_id, question_id=question_id, test_result_id=test_result_id).exists()

    # 計算使用者答題正確率
    @classmethod
    def get_accuracy(cls, user_id):
        records = cls.objects.filter(user_id=user_id)
        total = records.count()
        correct = records.filter(is_correct=True).count()
        return (correct / total * 100) if total else 0
    

class WeakTopic(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=50)  # 與 Question.topic 對應
    last_diagnosed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} 的弱項：{self.topic}"


class Explanation(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE)
    explanation_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50, default='gpt')

    def __str__(self):
        return f"詳解 - Q{self.question.id}"


class GptLog(models.Model):
    original_question = models.ForeignKey(Question, related_name='origin', on_delete=models.CASCADE)
    generated_question = models.ForeignKey(Question, related_name='generated', on_delete=models.CASCADE)
    topic = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GPT 出題記錄：{self.topic}"


class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} 對 Q{self.question.id} 的回饋"


class WrongQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) 
    question = models.ForeignKey(Question, on_delete=models.CASCADE) 
    confirmed = models.BooleanField(default=False) # 原有的：是否已在錯題本中確認/複習
    last_wrong_time = models.DateTimeField(auto_now=True) # 原有的：記錄最近一次答錯時間
    note = models.TextField(blank=True, null=True) # 原有的：筆記

    # --- 要求新增的欄位 ---
    is_fixed = models.BooleanField(default=False)  # 新增：是否已在「錯題挑戰」中修正此題
    created_dt = models.DateTimeField(auto_now_add=True) # 新增：這筆錯題記錄的建立時間
    fixed_dt = models.DateTimeField(null=True, blank=True)  # 新增：標記為已修正的時間 (可為空)
    # --- 新增欄位結束 ---

    class Meta:
        unique_together = ('user', 'question')

    def __str__(self):
        return f"{self.user.username} - {self.question.content[:50]}..."
    
    
