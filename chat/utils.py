def ensure_session_key(request):
    if not request.session.session_key:
        request.session.save()  # создаст session_key
    return request.session.session_key
