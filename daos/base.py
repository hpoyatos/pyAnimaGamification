from extensions import db

class BaseDAO:
    model = None

    @classmethod
    def get_all(cls):
        return cls.model.query.all()

    @classmethod
    def get_by_id(cls, record_id):
        return cls.model.query.get(record_id)

    @classmethod
    def create(cls, data):
        record = cls.model(**data)
        db.session.add(record)
        db.session.commit()
        return record

    @classmethod
    def update(cls, record_id, data):
        record = cls.get_by_id(record_id)
        if not record:
            return None
        for key, value in data.items():
            if hasattr(record, key):
                setattr(record, key, value)
        db.session.commit()
        return record

    @classmethod
    def delete(cls, record_id):
        record = cls.get_by_id(record_id)
        if not record:
            return False
        db.session.delete(record)
        db.session.commit()
        return True
