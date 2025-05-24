from django.db import models

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

    # 自行封裝方法：判斷是否已作答
    @classmethod
    def save_answer(cls, user_id, question, selected_option, test_result_id):       
        if not cls.has_answered(user_id, question.id, test_result_id):
            cls.objects.create(
                user_id=user_id,
                question=question,
                selected_option=selected_option,
                is_correct=(selected_option == question.answer),
                test_result_id=test_result_id
            )

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
