# core/repositories.py
from .models import User, WrongQuestion, Question, WeakTopic, TestRecord
from django.utils import timezone
from django.db.models import Min, Count
import random

class UserRepository:
    def get_user_by_id(self, user_id):
        """
        根據 user_id 獲取 User 物件。
        如果找不到，回傳 None。
        """
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

class WrongQuestionRepository:
    def get_or_create(self, user, question, defaults=None): #這是 S5 TestRecord.save_answer 會用到的
        """
        獲取或建立一筆 WrongQuestion 記錄。
        """
        return WrongQuestion.objects.get_or_create(user=user, question=question, defaults=defaults)

    def save_wrong_question(self, wrong_question_instance): # 這個可能目前 S5 沒直接用到，但保留著有好處
        """
        儲存 WrongQuestion 物件的變更。
        """
        wrong_question_instance.save()
    
    def update_wrong_question_fields(self, wrong_question_instance, fields_to_update=None): # 這是 S5 TestRecord.save_answer 會用到的
        """
        儲存 WrongQuestion 物件的特定欄位變更。
        """
        wrong_question_instance.save(update_fields=fields_to_update)

    def get_unconfirmed_by_user_and_topic(self, user, topic=None): # 這是 S5 wrong_questions_view 和 S6 diagnose_weakness_view 都會用到的
        """
        獲取指定使用者未確認的錯題，可選擇性地按主題篩選，並按最後答錯時間排序。
        """
        query = WrongQuestion.objects.filter(user=user, confirmed=False)
        if topic and topic != 'all': 
            query = query.filter(question__topic=topic)
        return query.order_by('-last_wrong_time')

    def get_distinct_topics_for_unconfirmed_by_user(self, user): # 這是 S5 wrong_questions_view 會用到的
        """
        獲取指定使用者未確認錯題中的所有不重複主題。
        """
        return WrongQuestion.objects.filter(user=user, confirmed=False) \
                                  .values_list('question__topic', flat=True) \
                                  .distinct() \
                                  .order_by('question__topic')
                                  
    # 這是 S6 diagnose_weakness_view 會用到的方法
    def get_sample_for_weakness_analysis(self, user, sample_count):
        """
        為弱點分析獲取指定使用者的錯題樣本。
        """
        # 注意：這裡的 all_user_wrong_questions 查詢邏輯，
        # 和 get_unconfirmed_by_user_and_topic(user=user, topic=None) 的初始 query 是一樣的。
        # 你可以考慮是否要直接呼叫 self.get_unconfirmed_by_user_and_topic(user=user) 來獲取 all_user_wrong_questions。
        # 但為了清晰，我暫時分開寫。
        all_user_wrong_questions = WrongQuestion.objects.filter(user=user, confirmed=False)
        
        actual_sample_count = min(len(all_user_wrong_questions), sample_count)
        
        if actual_sample_count > 0:
            return random.sample(list(all_user_wrong_questions), actual_sample_count)
        return []


class WeakTopicRepository:
    def update_or_create_weak_topic(self, user, topic_name):
        weak_topic, created = WeakTopic.objects.update_or_create(
            user=user,
            topic=topic_name,
            defaults={'last_diagnosed': timezone.now()} 
        )
        return weak_topic, created

    def get_weak_topics_for_user(self, user):
        return WeakTopic.objects.filter(user=user).order_by('-last_diagnosed')
    
    
class TestRecordRepository:
    def get_recent_test_session_summaries(self, user, limit=10):
        """
        獲取指定使用者最近的測驗摘要列表。
        每筆摘要包含：測驗日期、主題、總題數、答對題數、正確率、測驗結果ID。
        """
        # 1. 找出不重複的 test_result_id 及其對應的測驗日期，並按日期排序取最新的 N 筆
        test_sessions_query = TestRecord.objects.filter(user=user) \
                                           .values('test_result_id') \
                                           .annotate(test_date=Min('timestamp')) \
                                           .order_by('-test_date')[:limit]
        
        test_history_details = []
        for session_data in test_sessions_query:
            session_id = session_data['test_result_id']
            session_date = session_data['test_date']
            
            # 2. 對於每一個 session_id，獲取其所有答題記錄
            records_for_session = TestRecord.objects.filter(user=user, test_result_id=session_id)
            
            total_questions = records_for_session.count()
            if total_questions == 0:
                continue # 如果該次測驗沒有記錄，則跳過
            
            correct_questions = records_for_session.filter(is_correct=True).count()
            accuracy = round((correct_questions / total_questions) * 100, 2) if total_questions else 0
            
            # 3. 獲取該次測驗的主題 (以第一條記錄的題目主題為代表)
            first_record = records_for_session.select_related('question').first() # 使用 select_related 優化查詢
            test_topic = "未知主題"
            if first_record and first_record.question:
                test_topic = first_record.question.topic
            
            test_history_details.append({
                'test_date': session_date,
                'test_topic': test_topic,
                'total_questions': total_questions,
                'correct_questions': correct_questions,
                'accuracy': accuracy,
                'test_result_id': session_id, 
            })
        return test_history_details