from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import json
import os

@dataclass
class Task:
    id: int
    text: str
    done: bool
    created_at: datetime
    
    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'done': self.done,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data['id'],
            text=data['text'],
            done=data['done'],
            created_at=datetime.fromisoformat(data['created_at'])
        )

class TaskStorage:
    def __init__(self, filename: str = 'tasks.json'):
        self.filename = filename
        self.tasks: List[Task] = []
        self.load_tasks()
    
    def load_tasks(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(task_data) for task_data in data]
            except (json.JSONDecodeError, KeyError, ValueError):
                self.tasks = []
        else:
            self.tasks = []
    
    def save_tasks(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump([task.to_dict() for task in self.tasks], f, ensure_ascii=False, indent=2)
    
    def add_task(self, text: str) -> Task:
        new_id = max([task.id for task in self.tasks], default=0) + 1
        task = Task(
            id=new_id,
            text=text,
            done=False,
            created_at=datetime.now()
        )
        self.tasks.append(task)
        self.save_tasks()
        return task
    
    def get_tasks(self, user_id: int) -> List[Task]:
        return [task for task in self.tasks if not task.done]
    
    def mark_done(self, task_id: int) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.done = True
                self.save_tasks()
                return True
        return False
    
    def get_file_size_kb(self) -> float:
        if os.path.exists(self.filename):
            return os.path.getsize(self.filename) / 1024
        return 0