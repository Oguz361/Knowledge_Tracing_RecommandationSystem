from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict, Any 
from datetime import datetime 
from . import models
from passlib.context import CryptContext
import schemas
from schemas.teacher_schemas import TeacherCreate
from schemas.class_schemas import ClassCreate
from schemas.student_schemas import StudentCreate
from schemas.skill_schemas import SkillCreate
from schemas.problem_schemas import ProblemCreate
from schemas.interaction_schemas import InteractionCreate, InteractionCSVRow
from sqlalchemy.orm import joinedload

# Passwort-Hashing-Kontext für Teacher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# CRUD Operationen für Teacher
def get_teacher(db: Session, teacher_id: int) -> Optional[models.Teacher]:
    return db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()

def get_teacher_by_username(db: Session, username: str) -> Optional[models.Teacher]:
    return db.query(models.Teacher).filter(models.Teacher.username == username).first()

def get_teachers(db: Session, skip: int = 0, limit: int = 100) -> List[models.Teacher]:
    return db.query(models.Teacher).offset(skip).limit(limit).all()

def create_teacher(db: Session, teacher: schemas.TeacherCreate) -> models.Teacher:
    hashed_password = get_password_hash(teacher.password)
    db_teacher = models.Teacher(username=teacher.username, hashed_password=hashed_password)
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)
    return db_teacher

# CRUD Operationen für Class
def get_class(db: Session, class_id: int) -> Optional[models.Class]:
    return db.query(models.Class).filter(models.Class.id == class_id).first()

def get_classes_by_teacher(db: Session, teacher_id: int, skip: int = 0, limit: int = 100) -> List[models.Class]:
    return db.query(models.Class).filter(models.Class.teacher_id == teacher_id).offset(skip).limit(limit).all()

def create_class_for_teacher(db: Session, class_data: schemas.ClassCreate, teacher_id: int) -> models.Class:
    db_class = models.Class(**class_data.model_dump(), teacher_id=teacher_id)
    db.add(db_class)
    db.commit()
    db.refresh(db_class)
    return db_class

def update_class(db: Session, class_id: int, class_update_data: schemas.ClassCreate) -> Optional[models.Class]:
    db_class = get_class(db, class_id)
    if db_class:
        db_class.name = class_update_data.name
        db_class.description = class_update_data.description
        db.commit()
        db.refresh(db_class)
    return db_class

def delete_class(db: Session, class_id: int) -> Optional[models.Class]:
    db_class = get_class(db, class_id)
    if not db_class:
        return None
    
    active_student_count = db.query(models.Student).filter(
        models.Student.class_id == class_id,
        models.Student.is_deleted == False
    ).count()
    
    if active_student_count > 0:
        raise ValueError(f"Klasse kann nicht gelöscht werden. Bitte erst die {active_student_count} Schüler löschen.")
    
    deleted_students = db.query(models.Student).filter(
        models.Student.class_id == class_id,
        models.Student.is_deleted == True
    ).all()
    
    for student in deleted_students:
        db.delete(student)
    
    db.delete(db_class)
    db.commit()
    return db_class

# CRUD Operationen für Student
def get_student(db: Session, student_id: int) -> Optional[models.Student]:
    return db.query(models.Student).filter(models.Student.id == student_id).first()

def get_students_by_class(db: Session, class_id: int, skip: int = 0, limit: int = 100) -> List[models.Student]:
    query = db.query(models.Student).filter(models.Student.class_id == class_id)
    
    # Wenn is_deleted existiert filtert gelöschte Schüler aus
    if hasattr(models.Student, 'is_deleted'):
        query = query.filter(models.Student.is_deleted == False)
    
    return query.offset(skip).limit(limit).all()

def search_students_in_class(db: Session, class_id: int, query: str, skip: int = 0, limit: int = 100) -> List[models.Student]:
    search_query = f"%{query}%"
    return db.query(models.Student).filter(
        models.Student.class_id == class_id,
        (models.Student.first_name.ilike(search_query) | models.Student.last_name.ilike(search_query))
    ).offset(skip).limit(limit).all()

def create_student_in_class(db: Session, student: schemas.StudentCreate, class_id: int) -> models.Student:
    db_student = models.Student(**student.model_dump(), class_id=class_id, last_interaction_update_timestamp=datetime.utcnow())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student

def update_student(db: Session, student_id: int, student_update_data: schemas.StudentCreate) -> Optional[models.Student]:
    db_student = get_student(db, student_id)
    if db_student:
        db_student.first_name = student_update_data.first_name
        db_student.last_name = student_update_data.last_name
        db.commit()
        db.refresh(db_student)
    return db_student
    
def update_student_last_interaction_timestamp(db: Session, student_id: int, timestamp: datetime = None) -> Optional[models.Student]:
    db_student = get_student(db, student_id)
    if db_student:
        db_student.last_interaction_update_timestamp = timestamp if timestamp else datetime.utcnow()
        db.commit()
        db.refresh(db_student)
    return db_student

def delete_student(db: Session, student_id: int) -> Optional[models.Student]:
    db_student = get_student(db, student_id)
    if db_student:
        db_student.is_deleted = True
        db_student.deleted_at = datetime.utcnow()
        db.commit()
        db.refresh(db_student)
    return db_student

# CRUD Operationen für Skill
def get_skill(db: Session, skill_id: int) -> Optional[models.Skill]: 
    return db.query(models.Skill).filter(models.Skill.id == skill_id).first()

def get_skill_by_internal_idx(db: Session, internal_idx: int) -> Optional[models.Skill]:
    return db.query(models.Skill).filter(models.Skill.internal_idx == internal_idx).first()

def get_skill_by_name(db: Session, name: str) -> Optional[models.Skill]:
    return db.query(models.Skill).filter(models.Skill.name == name).first()

def get_skill_by_original_id(db: Session, original_skill_id: str) -> Optional[models.Skill]:
    return db.query(models.Skill).filter(models.Skill.original_skill_id == original_skill_id).first()

def get_skills(db: Session, skip: int = 0, limit: int = 102) -> List[models.Skill]: 
    return db.query(models.Skill).offset(skip).limit(limit).all()

def create_skill(db: Session, skill: schemas.SkillCreate) -> models.Skill:
    db_skill = models.Skill(
        internal_idx=skill.internal_idx,
        original_skill_id=skill.original_skill_id,
        name=skill.name
    )
    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)
    return db_skill

# CRUD Operationen für Problem
def get_problem(db: Session, problem_id: int) -> Optional[models.Problem]: 
    return db.query(models.Problem).filter(models.Problem.id == problem_id).first()

def get_problem_by_internal_idx(db: Session, internal_idx: int) -> Optional[models.Problem]:
    return db.query(models.Problem).filter(models.Problem.internal_idx == internal_idx).first()

def get_problem_by_original_id(db: Session, original_problem_id: str) -> Optional[models.Problem]:
    return db.query(models.Problem).filter(models.Problem.original_problem_id == original_problem_id).first()

def get_problems_by_skill_id(db: Session, skill_id: int, skip: int = 0, limit: int = 100) -> List[models.Problem]:
    return db.query(models.Problem).filter(models.Problem.skill_id == skill_id).offset(skip).limit(limit).all()

def get_problems_by_skill_internal_idx(db: Session, skill_internal_idx: int, skip: int = 0, limit: int = 3200) -> List[models.Problem]:
    skill = get_skill_by_internal_idx(db, internal_idx=skill_internal_idx)
    if not skill:
        return []
    return db.query(models.Problem).filter(models.Problem.skill_id == skill.id).offset(skip).limit(limit).all()

def create_problem(db: Session, problem: schemas.ProblemCreate) -> models.Problem:
    db_skill = get_skill_by_internal_idx(db, internal_idx=problem.skill_internal_idx)
    if not db_skill:
        raise ValueError(f"Skill mit internal_idx {problem.skill_internal_idx} nicht gefunden")
    
    db_problem = models.Problem(
        internal_idx=problem.internal_idx,
        original_problem_id=problem.original_problem_id,
        description_placeholder=problem.description_placeholder,
        skill_id=db_skill.id,
        difficulty_mu_q=problem.difficulty_mu_q 
    )
    db.add(db_problem)
    db.commit()
    db.refresh(db_problem)
    return db_problem

def update_problem_mu_q(db: Session, problem_internal_idx: int, mu_q: float) -> Optional[models.Problem]:
    db_problem = get_problem_by_internal_idx(db, internal_idx=problem_internal_idx)
    if db_problem:
        db_problem.difficulty_mu_q = mu_q
        db.commit()
        db.refresh(db_problem)
    return db_problem

# CRUD Operationen für Interaction
def get_interaction(db: Session, interaction_id: int) -> Optional[models.Interaction]:
    return db.query(models.Interaction).filter(models.Interaction.id == interaction_id).first()

def get_student_interactions(
    db: Session, 
    student_id: int, 
    limit: Optional[int] = None, 
    sort_desc: bool = True, 
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skill_id: Optional[int] = None
) -> List[models.Interaction]:
    """
    Ruft Interaktionen eines Schülers mit Eager Loading für Relationships.
    """
    query = db.query(models.Interaction)\
        .options(
            joinedload(models.Interaction.problem),
            joinedload(models.Interaction.skill)
        )\
        .filter(models.Interaction.student_id == student_id)
    
    if start_date:
        query = query.filter(models.Interaction.timestamp >= start_date)
    if end_date:
        query = query.filter(models.Interaction.timestamp <= end_date)
    if skill_id:
        query = query.filter(models.Interaction.skill_id == skill_id)
    
    if sort_desc:
        query = query.order_by(desc(models.Interaction.timestamp))
    else:
        query = query.order_by(models.Interaction.timestamp)
    
    if limit:
        query = query.limit(limit)
    
    return query.all()

def create_interaction(db: Session, interaction: schemas.InteractionCreate, student_id: int) -> models.Interaction:
    db_problem = get_problem(db, interaction.problem_db_id)
    if not db_problem:
        raise ValueError(f"Problem mit ID {interaction.problem_db_id} nicht gefunden")
    
    if db_problem.skill_id != interaction.skill_db_id:
        raise ValueError(f"Problem {interaction.problem_db_id} gehört nicht zu Skill {interaction.skill_db_id}")
    
    db_interaction = models.Interaction(
        student_id=student_id,
        problem_id=interaction.problem_db_id,
        skill_id=interaction.skill_db_id,
        is_correct=interaction.is_correct,
        timestamp=interaction.timestamp
    )
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    update_student_last_interaction_timestamp(db, student_id=student_id, timestamp=interaction.timestamp)
    return db_interaction

def create_interaction_from_csv(db: Session, csv_row: schemas.InteractionCSVRow, student_id: int) -> Optional[models.Interaction]:
    """Helper-Funktion für CSV-Import - konvertiert Original-IDs zu DB-IDs"""
    # Finde Problem
    db_problem = get_problem_by_original_id(db, csv_row.problem_original_id)
    if not db_problem:
        return None
    
    # Finde Skill
    db_skill = get_skill_by_original_id(db, csv_row.skill_original_id)
    if not db_skill:
        return None
    
    # Erstelle InteractionCreate Schema
    interaction_data = schemas.InteractionCreate(
        problem_db_id=db_problem.id,
        skill_db_id=db_skill.id,
        is_correct=csv_row.is_correct,
        timestamp=csv_row.timestamp
    )
    
    try:
        return create_interaction(db, interaction_data, student_id)
    except ValueError:
        return None

def get_student_statistics(db: Session, student_id: int) -> Dict[str, Any]:
    """
    Berechnet Statistiken für einen Schüler.
    
    Returns:
        Dict mit total_interactions, correct_interactions, accuracy, skills_practiced, etc.
    """
    from sqlalchemy import func
    
    student = get_student(db, student_id)
    if not student:
        return {}  
    
    total = db.query(func.count(models.Interaction.id))\
        .filter(models.Interaction.student_id == student_id).scalar() or 0
    
    correct = db.query(func.count(models.Interaction.id))\
        .filter(
            models.Interaction.student_id == student_id,
            models.Interaction.is_correct == True
        ).scalar() or 0
    
    skills_practiced = db.query(func.count(func.distinct(models.Interaction.skill_id)))\
        .filter(models.Interaction.student_id == student_id).scalar() or 0
    
    last_activity = db.query(func.max(models.Interaction.timestamp))\
        .filter(models.Interaction.student_id == student_id).scalar()
    
    problems_attempted = db.query(func.count(func.distinct(models.Interaction.problem_id)))\
        .filter(models.Interaction.student_id == student_id).scalar() or 0
    
    return {
        "total_interactions": total,
        "correct_interactions": correct,
        "incorrect_interactions": total - correct,
        "accuracy": round((correct / total * 100) if total > 0 else 0, 2),
        "skills_practiced": skills_practiced,
        "problems_attempted": problems_attempted,
        "last_activity": last_activity.isoformat() if last_activity else None,
        "activity_status": "active" if last_activity else "no_activity"
    }

def get_classes_for_dashboard(db: Session, teacher_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Ruft Klassen einer Lehrkraft mit der Anzahl der (nicht gelöschten) Schüler ab.
    Gibt eine Liste von Dictionaries zurück, die für ClassDashboardRead geeignet sind.
    """
    from .models import Student, Class  

    student_count_subquery = (
        db.query(
            Student.class_id,
            func.count(Student.id).label("student_count")
        )
        .filter(Student.is_deleted == False)
        .group_by(Student.class_id)
        .subquery()
    )

    query_result = (
        db.query(
            Class.id,
            Class.name,
            func.coalesce(student_count_subquery.c.student_count, 0).label("student_count")
        )
        .outerjoin(student_count_subquery, Class.id == student_count_subquery.c.class_id)
        .filter(Class.teacher_id == teacher_id)
        .order_by(desc(Class.created_at)) 
        .limit(limit)
        .all()
    )

    dashboard_classes_data = []
    for row in query_result:
        dashboard_classes_data.append({
            "id": row.id,
            "name": row.name,
            "student_count": row.student_count
        })

    return dashboard_classes_data