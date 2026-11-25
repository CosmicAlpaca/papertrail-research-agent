from server import grounded_chat
from server.agent import validate_judgments

def test_chat_discards_unknown_sources_and_fabricated_quotes(monkeypatch):
    papers = [{'id':'p1', 'title':'A study of graph explanations', 'abstract':'We evaluate on molecular graphs.'}]
    monkeypatch.setattr(grounded_chat, 'json_completion', lambda *args: {'claims': [
        {'paper_id':'p2','text':'Invented paper','quote':'We evaluate on molecular graphs.'},
        {'paper_id':'p1','text':'Invented evidence','quote':'We beat every baseline on all datasets.'},
        {'paper_id':'p1','text':'Molecular graphs are evaluated.','quote':'We evaluate on molecular graphs.'}]})
    result = grounded_chat.answer('What data is used?', papers)
    assert len(result['claims']) == 1
    assert result['claims'][0]['paper_id'] == 'p1'
    assert result['claims'][0]['text'] == 'Molecular graphs are evaluated.'

def test_malformed_model_judgments_remain_uncertain():
    papers = [{'id':'p1','title':'A useful paper','abstract':'No experimental details are available here.'}]
    validate_judgments(papers,[{'id':'c1','text':'Uses real datasets'}],{'judgments':None})
    assert papers[0]['criteria'][0]['status'] == 'uncertain'
