from sqlalchemy.orm import Session
from ..db.models import Literature, Segment
from ..db.database import SessionLocal

def seed_pali_data(db: Session):
    """Seeds the Pali database with initial data if empty."""
    try:
        # Check if data exists
        count = db.query(Literature).count()
        if count > 0:
            print(f"Pali DB already has {count} literatures. Skipping seed.")
            return

        print("Seeding Pali database with sample data...")
        
        # 1. Digha Nikaya (Long Discourses)
        dn = Literature(
            id="dn",
            title="Dīgha Nikāya",
            name="長部 (장부)",
            pali_name="Dīgha Nikāya",
            pitaka="Sutta",
            nikaya="Dighanikaya",
            category="Nikaya",
            description="Collection of Long Discourses",
            total_segments=34,
            translated_segments=0,
            status="parsed"
        )
        db.add(dn)

        # 2. Majjhima Nikaya (Middle Discourses)
        mn = Literature(
            id="mn",
            title="Majjhima Nikāya",
            name="中部 (중부)",
            pali_name="Majjhima Nikāya",
            pitaka="Sutta",
            nikaya="Majjhimanikaya",
            category="Nikaya",
            description="Collection of Middle Length Discourses",
            total_segments=152,
            translated_segments=0,
            status="parsed"
        )
        db.add(mn)

        # 3. Samyutta Nikaya (Connected Discourses)
        sn = Literature(
            id="sn",
            title="Saṃyutta Nikāya",
            name="相應部 (상응부)",
            pali_name="Saṃyutta Nikāya",
            pitaka="Sutta",
            nikaya="Samyuttanikaya",
            category="Nikaya",
            description="Collection of Connected Discourses",
            total_segments=56,
            translated_segments=0,
            status="parsed"
        )
        db.add(sn)

        db.commit()
        
        # Add a sample sutta to Digha Nikaya
        # DN 1: Brahmajala Sutta
        dn1_seg = Segment(
            literature_id="dn",
            paragraph_id=1,
            original_text="Evaṃ me sutaṃ— ekaṃ samayaṃ bhagavā antarā ca rājagahaṃ antarā ca nāḷandaṃ addhānamaggappaṭipanno hoti mahatā bhikkhusaṅghena saddhiṃ pañcamattehi bhikkhusatehi.",
            translation={"ko": "이와 같이 나는 들었다. 한때 세존께서 라자가하와 날란다 사이의 긴 길을 걷고 계셨다. 500명의 비구 대중과 함께."},
            vagga_id=1,
            vagga_name="Silakkhandhavagga",
            sutta_id=1,
            sutta_name="Brahmajāla Sutta",
            page_number=1,
            is_translated=True
        )
        db.add(dn1_seg)
        
        db.commit()
        print("Successfully seeded Pali database.")
        
    except Exception as e:
        print(f"Error seeding Pali data: {e}")
        db.rollback()
