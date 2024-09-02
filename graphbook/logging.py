# TODO: make logging singleton
def log(msg: str, type: str = "info"):
    # class = prev_frame.f_locals['self'].__class__()
    # caller = prev_frame.f_locals['self']
    print(f"[{type}] {msg}")
    return msg