from graphbook.steps.base import Step, DataRecord
import sys
# sys.path.append("src")

def test_set_child_is_idempotent():
    a = Step("A", None)
    b = Step("B", None)
    a.set_child(b)
    a.set_child(b)
    assert len(a.children["out"]) == 1
    
def test_remove_children():
    a = Step("A", None)
    b = Step("B", None)
    a.set_child(b)
    a.remove_children()
    assert len(a.children) == 0
    assert len(b.parents) == 0
