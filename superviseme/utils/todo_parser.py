"""
Todo Reference Parser Utility

This module provides functionality to parse todo references in text content
and create links between updates/feedback and todos.
"""
import re
import time
from superviseme.models import Todo, Todo_Reference, Thesis_Update
from superviseme import db


def parse_todo_references(text):
    """
    Parse todo references from text using patterns like:
    - @todo:1 (reference to todo ID 1)
    - @todo:complete-literature-review (reference by todo title slug)
    - #todo-1 (alternative syntax)
    
    Returns list of todo IDs referenced
    """
    todo_refs = []
    
    # Pattern for @todo:ID or #todo-ID
    id_pattern = r'[@#]todo[-:](\d+)'
    id_matches = re.findall(id_pattern, text, re.IGNORECASE)
    todo_refs.extend([int(match) for match in id_matches])
    
    # Pattern for @todo:"title" or @todo:title-slug
    title_pattern = r'@todo:"([^"]+)"|@todo:([a-zA-Z0-9-_]+)'
    title_matches = re.findall(title_pattern, text, re.IGNORECASE)
    
    for quoted_title, slug_title in title_matches:
        title_to_search = quoted_title if quoted_title else slug_title.replace('-', ' ')
        # Find todos by title (case insensitive partial match)
        todos = Todo.query.filter(Todo.title.ilike(f'%{title_to_search}%')).all()
        todo_refs.extend([todo.id for todo in todos])
    
    return list(set(todo_refs))  # Remove duplicates


def create_todo_references(update_id, todo_ids):
    """
    Create Todo_Reference entries for the given update and todo IDs
    """
    current_time = int(time.time())
    
    # Remove existing references for this update
    Todo_Reference.query.filter_by(update_id=update_id).delete()
    
    # Create new references
    for todo_id in todo_ids:
        # Verify todo exists
        todo = Todo.query.get(todo_id)
        if todo:
            reference = Todo_Reference(
                update_id=update_id,
                todo_id=todo_id,
                created_at=current_time
            )
            db.session.add(reference)
    
    db.session.commit()


def format_text_with_todo_links(text, base_url="/"):
    """
    Replace todo references in text with HTML links
    
    Args:
        text: The text content to process
        base_url: Base URL for todo links (default: "/")
    
    Returns:
        HTML string with todo references converted to links
    """
    if not text:
        return text
    
    def replace_todo_ref(match):
        todo_id = match.group(1)
        try:
            todo = Todo.query.get(int(todo_id))
            if todo:
                return f'<a href="{base_url}todo/{todo_id}" class="todo-reference badge badge-primary" title="{todo.title}">@todo:{todo_id}</a>'
            else:
                return f'<span class="todo-reference-invalid badge badge-secondary">@todo:{todo_id}</span>'
        except:
            return match.group(0)
    
    def replace_hash_todo_ref(match):
        todo_id = match.group(1)
        try:
            todo = Todo.query.get(int(todo_id))
            if todo:
                return f'<a href="{base_url}todo/{todo_id}" class="todo-reference badge badge-primary" title="{todo.title}">#todo-{todo_id}</a>'
            else:
                return f'<span class="todo-reference-invalid badge badge-secondary">#todo-{todo_id}</span>'
        except:
            return match.group(0)
    
    # Replace @todo:ID patterns
    text = re.sub(r'@todo:(\d+)', replace_todo_ref, text)
    # Replace #todo-ID patterns  
    text = re.sub(r'#todo-(\d+)', replace_hash_todo_ref, text)
    
    return text


def get_todos_for_thesis(thesis_id):
    """
    Get all todos for a specific thesis, formatted for dropdown selection
    """
    todos = Todo.query.filter_by(thesis_id=thesis_id).order_by(Todo.created_at.desc()).all()
    return [{'id': todo.id, 'title': todo.title, 'status': todo.status} for todo in todos]


def get_todo_references_summary(update_id):
    """
    Get summary of todo references for an update
    """
    references = Todo_Reference.query.filter_by(update_id=update_id).all()
    todos = []
    for ref in references:
        if ref.todo:
            todos.append({
                'id': ref.todo.id,
                'title': ref.todo.title,
                'status': ref.todo.status,
                'priority': ref.todo.priority
            })
    return todos