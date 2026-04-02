from django.http import JsonResponse


def health_check(_request):
    return JsonResponse({'status': 'ok'})


def home(_request):
    return JsonResponse({'message': 'Welcome to Roam Map API'})

