from ..extensions import db

class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    ownerid = db.Column(db.Integer, nullable=True)
    fullname = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), nullable=True, default="lead")
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ownerid": self.ownerid,
            "fullname": self.fullname,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "status": self.status,
            "notes": self.notes,
        }
