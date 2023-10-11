class TaskData:
    def __init__(self,task):
        self.task_dic = task.to_dict()
    
    def task_title(self):
        return self.task_dic['task']
    
    def task_created_date(self):
        return self.task_dic['added']
    
    def task_remind_data(self):
        return self.task_dic['next_reminder_time']
    
    def task_status(self):
        return self.task_dic['status']
    
    def task_category(self):
        if 'category' in self.task_dic:
            return self.task_dic['category']
        else:
            return None
        

