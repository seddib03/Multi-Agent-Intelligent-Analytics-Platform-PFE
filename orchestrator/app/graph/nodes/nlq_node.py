from app.graph.state import OrchestratorState
from app.utils.async_utils import run_async

def nlq_node(state: OrchestratorState) -> OrchestratorState:
    """
    Sprint 1 mock (mots-clés) → remplacé.
    
    Pourquoi ce node est maintenant un pass-through ?
    
    Selon le PV de la collègue, le NLQ Agent (chatbot) est activé
    APRÈS le dashboard global, pas au début du pipeline.
    
    Le flux correct est :
    1. /detect-sector  → fait par sector_detection_node (ci-dessus)
    2. Dashboard affiché à l'utilisateur
    3. /chat           → activé quand l'utilisateur pose une question
                         spécifique (géré par dispatch_node)
    
    Donc ce node ne fait rien ici — il laisse juste passer le state.
    """
    state.processing_steps.append(
        "nlq_node → pass-through "
        "(NLQ chatbot activé après dashboard via dispatch_node)"
    )
    return state
