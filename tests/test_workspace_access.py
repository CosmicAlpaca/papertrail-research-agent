from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from server import main, db

def test_workspace_ownership_and_database_persistence(tmp_path, monkeypatch):
    original = db.engine
    test_engine=create_engine('sqlite:///'+str(tmp_path/'isolated.sqlite3'),connect_args={'check_same_thread':False})
    monkeypatch.setattr(main,'engine',test_engine)
    monkeypatch.setattr(db,'engine',test_engine)
    monkeypatch.setattr(main.agent,'warm_reranker',lambda:None)
    db.Session.configure(bind=test_engine)
    try:
        with TestClient(main.app) as client:
            one=client.post('/api/workspaces',json={}).json()
            two=client.post('/api/workspaces',json={}).json()
            with db.Session() as session:
                owner=session.query(db.Workspace).filter_by(token_hash=db.token_hash(one['token'])).one()
                session.add(db.Run(id='private-run',workspace_id=owner.id,request={'plan':{'question':'Private research'}},result={},events=[],feedback={}))
                session.commit()
            assert client.get('/api/runs/private-run',headers={'Authorization':'Bearer '+one['token']}).status_code==200
            assert client.get('/api/runs/private-run',headers={'Authorization':'Bearer '+two['token']}).status_code==404
            assert client.get('/api/runs/private-run').status_code==401
    finally:
        db.Session.configure(bind=original)
        test_engine.dispose()
