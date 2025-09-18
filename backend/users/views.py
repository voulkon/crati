from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from users.models import SavedEntity, SavedDecision, SearchHistory, VisitedEntity

class UserDataViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get', 'post'])
    def saved_entities(self, request):
        if request.method == 'GET':
            entities = SavedEntity.objects.filter(user=request.user)
            # Add pagination here
            return Response([{
                'id': e.id,
                'entity_type': e.entity_type,
                'entity_id': e.entity_id,
                'entity_name': e.entity_name,
                'notes': e.notes,
                'created_at': e.created_at,
                'updated_at': e.updated_at
            } for e in entities])
        
        elif request.method == 'POST':
            # Check user's limit
            if request.user.saved_entities.count() >= request.user.max_saved_items:
                return Response({
                    'error': 'Maximum saved entities limit reached'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            data = request.data
            entity, created = SavedEntity.objects.get_or_create(
                user=request.user,
                entity_type=data['entity_type'],
                entity_id=data['entity_id'],
                defaults={
                    'entity_name': data['entity_name'],
                    'entity_data': data.get('entity_data'),
                    'notes': data.get('notes', '')
                }
            )
            
            if not created:
                # Update existing
                entity.notes = data.get('notes', entity.notes)
                entity.save()
            
            return Response({
                'id': entity.id,
                'created': created
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def search_history(self, request):
        history = SearchHistory.objects.filter(user=request.user)[:20]
        return Response([{
            'id': h.id,
            'query': h.query,
            'search_type': h.search_type,
            'results_count': h.results_count,
            'created_at': h.created_at
        } for h in history])
    
    @action(detail=False, methods=['post'])
    def track_visit(self, request):
        """Track when user visits an entity"""
        data = request.data
        entity, created = VisitedEntity.objects.get_or_create(
            user=request.user,
            entity_type=data['entity_type'],
            entity_id=data['entity_id'],
            defaults={
                'entity_name': data['entity_name']
            }
        )
        
        if not created:
            entity.visit_count += 1
            entity.save()
        
        return Response({'tracked': True})
    
    @action(detail=False, methods=['get'])
    def user_preferences(self, request):
        return Response({
            'theme': request.user.preferred_theme,
            'palette': request.user.preferred_palette,
            'layout': request.user.preferred_layout
        })
    
    @action(detail=False, methods=['patch'])
    def update_preferences(self, request):
        user = request.user
        data = request.data
        
        if 'theme' in data:
            user.preferred_theme = data['theme']
        if 'palette' in data:
            user.preferred_palette = data['palette']
        if 'layout' in data:
            user.preferred_layout = data['layout']
        
        user.save()
        return Response({'updated': True})from django.shortcuts import render

# Create your views here.
