"""
Diagnosis & Recommendation Agent - Combined analysis and recommendations.

This agent analyzes results from multiple agents and generates both
diagnosis (root causes, severity) and actionable recommendations in a single call.
"""
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic

from ..core.config import settings
from ..core.telemetry import get_logger


logger = get_logger(__name__)


class DiagnosisRecommendationAgent:
    """
    Combined Diagnosis & Recommendation Agent.

    Analyzes results from multiple specialist agents and generates both:
    - Diagnosis (root causes, correlations, severity)
    - Recommendations (prioritized, actionable)
    
    All in a single LLM call for efficiency.
    """

    def __init__(self):
        """Initialize Combined Agent."""
        self.llm = ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )

    async def analyze_and_recommend(
        self,
        agent_results: Dict[str, Any],
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        gate_warnings: Optional[List[str]] = None,
        review_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze agent results and generate recommendations in one call.

        Args:
            agent_results: Dict of {agent_name: AgentOutput}
            query: Original user query
            conversation_history: Optional list of previous messages for context
            gate_warnings: Optional list of warnings from gate validation

        Returns:
            Dict with:
            - diagnosis: Dict with issues, root_causes, severity, correlations, summary
            - recommendations: List[Dict] - Prioritized recommendations
            - confidence: float - Confidence in recommendations
            - action_plan: str - Summary action plan
        """
        import json

        # Extract key information from each agent
        agent_summaries = {}
        all_issues = []

        for agent_name, output in agent_results.items():
            # Include full response for analysis (not truncated)
            agent_summaries[agent_name] = {
                "response": output.response if output.response else "",
                "confidence": output.confidence,
                "tools_used": output.tools_used,
                "agent_name": output.agent_name if hasattr(output, 'agent_name') else agent_name
            }
            all_issues.extend(self._extract_issues_from_response(output.response))

        # Build context section
        context_sections = []
        
        # Add conversation history if available (truncated to last 3 messages for relevance)
        if conversation_history:
            recent_history = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            context_sections.append("CONVERSATION CONTEXT (recent messages):")
            for msg in recent_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                # Truncate long messages
                if len(content) > 200:
                    content = content[:200] + "..."
                context_sections.append(f"- {role.upper()}: {content}")
        
        # Add gate warnings if available
        if gate_warnings:
            context_sections.append(f"\nGATE VALIDATION WARNINGS:")
            for warning in gate_warnings:
                context_sections.append(f"- {warning}")
        
        # Add review context if available (consistency check results from orchestrator)
        if review_context:
            review_section = "\nORCHESTRATOR REVIEW FINDINGS:"
            review_section += f"\n- Results Consistent: {review_context.get('consistent', True)}"
            
            if review_context.get("expected_time_period"):
                review_section += f"\n- Expected Time Period: {review_context['expected_time_period']}"
            
            if review_context.get("expected_dates", {}).get("start_date"):
                review_section += f"\n- Expected Date Range: {review_context['expected_dates']['start_date']} to {review_context['expected_dates']['end_date']}"
            
            if review_context.get("actual_time_periods"):
                review_section += "\n- Actual Time Periods Used by Agents:"
                for agent, period in review_context["actual_time_periods"].items():
                    review_section += f"\n  * {agent}: {period}"
            
            mismatches = review_context.get("mismatches", [])
            if mismatches:
                review_section += "\n- Inconsistencies Detected:"
                for mismatch in mismatches:
                    review_section += f"\n  * {mismatch.get('agent', 'unknown')}: Expected {mismatch.get('expected', 'unknown')}, Got {mismatch.get('actual', 'unknown')}"
            
            if review_context.get("requery_count", 0) > 0:
                review_section += f"\n- Note: Agents were re-queried {review_context['requery_count']} time(s) to ensure consistency"
            
            if review_context.get("comparison_mode"):
                review_section += "\n- Comparison Mode: True (comparing multiple agents/data sources)"
            
            context_sections.append(review_section)
        
        context_text = "\n".join(context_sections) if context_sections else "None"

        # Include key agent results for context (but keep it concise)
        agent_context = ""
        if agent_results:
            agent_summaries_short = []
            for agent_name, output in list(agent_results.items())[:2]:  # Limit to 2 agents
                if hasattr(output, 'response') and output.response:
                    # Truncate to first 300 chars per agent to keep prompt short
                    response_preview = output.response[:300] + "..." if len(output.response) > 300 else output.response
                    agent_summaries_short.append(f"{agent_name}: {response_preview}")
            if agent_summaries_short:
                agent_context = f"\n\nAgent Findings (Summary):\n" + "\n".join(f"- {s}" for s in agent_summaries_short)

        # Combined prompt for diagnosis + recommendations
        combined_prompt = f"""You are a DV360 analysis expert. Analyze agent results and provide both diagnosis and recommendations.

User Query: "{query}"

{context_text}

Agent Results (Full Responses):
{json.dumps(agent_summaries, indent=2, ensure_ascii=False)}

Identified Issues:
{chr(10).join(f'- {issue}' for issue in all_issues) if all_issues else 'None identified'}

Your task:
1. DIAGNOSIS: Identify ROOT CAUSES, CORRELATIONS, SEVERITY, and SUMMARY
2. RECOMMENDATIONS: Generate 3-4 prioritized, actionable recommendations that address root causes

Respond in this exact format:

DIAGNOSIS:
ROOT_CAUSES:
- [List root causes, one per line]

CORRELATIONS:
- [List correlations between agent findings]

SEVERITY: [critical/high/medium/low]

SUMMARY: [2-3 sentence summary of the diagnosis]

RECOMMENDATIONS:
RECOMMENDATION 1:
Priority: [high/medium/low]
Action: [Specific action]
Reason: [Why this helps]
Expected Impact: [What improves]

RECOMMENDATION 2:
Priority: [high/medium/low]
Action: [Specific action]
Reason: [Why this helps]
Expected Impact: [What improves]

(Continue for 3-4 recommendations)

CONFIDENCE: [0.0-1.0]
ACTION_PLAN: [2-3 sentence summary of overall action plan]

Your analysis:"""

        try:
            messages = [
                SystemMessage(content="You are a DV360 analysis expert providing both diagnosis and recommendations."),
                HumanMessage(content=combined_prompt)
            ]

            response = self.llm.invoke(messages)
            response_text = response.content.strip()

            logger.info("Combined analysis LLM response", response_preview=response_text[:200])

            # Parse response
            diagnosis = self._parse_diagnosis(response_text)
            recommendations, confidence, action_plan = self._parse_recommendations(response_text)

            logger.info(
                "Combined analysis complete",
                root_causes_count=len(diagnosis.get("root_causes", [])),
                recommendations_count=len(recommendations),
                severity=diagnosis.get("severity"),
                confidence=confidence
            )

            return {
                "diagnosis": diagnosis,
                "recommendations": recommendations,
                "confidence": confidence,
                "action_plan": action_plan,
                "correlations": diagnosis.get("correlations", []),
                "severity_assessment": diagnosis.get("severity", "medium"),
                "raw_response": response_text
            }

        except Exception as e:
            logger.error("Combined analysis failed", error_message=str(e))
            
            # Fallback: return basic structure
            return {
                "diagnosis": {
                    "issues": all_issues,
                    "root_causes": ["Unable to determine root causes"],
                    "severity": "medium",
                    "correlations": [],
                    "summary": f"Analysis failed: {str(e)}",
                    "raw_response": None
                },
                "recommendations": [],
                "confidence": 0.5,
                "action_plan": "Review individual agent recommendations",
                "correlations": [],
                "severity_assessment": "medium",
                "raw_response": None
            }

    def _parse_diagnosis(self, response_text: str) -> Dict[str, Any]:
        """Parse diagnosis section from response."""
        root_causes = []
        correlations = []
        severity = "medium"
        summary = ""

        current_section = None
        in_diagnosis = False
        
        for line in response_text.split('\n'):
            line = line.strip()
            
            if line.startswith("DIAGNOSIS:"):
                in_diagnosis = True
                continue
            elif line.startswith("RECOMMENDATIONS:"):
                break  # Stop parsing when we hit recommendations
            
            if not in_diagnosis:
                continue
                
            if line.startswith("ROOT_CAUSES:"):
                current_section = "root_causes"
            elif line.startswith("CORRELATIONS:"):
                current_section = "correlations"
            elif line.startswith("SEVERITY:"):
                severity_text = line.replace("SEVERITY:", "").strip().lower()
                if severity_text in ["critical", "high", "medium", "low"]:
                    severity = severity_text
                current_section = None
            elif line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
                current_section = None
            elif line.startswith("-") and current_section:
                item = line.lstrip("- ").strip()
                if current_section == "root_causes":
                    root_causes.append(item)
                elif current_section == "correlations":
                    correlations.append(item)

        return {
            "root_causes": root_causes,
            "correlations": correlations,
            "severity": severity,
            "summary": summary or "No clear diagnosis available"
        }

    def _parse_recommendations(self, response_text: str) -> tuple[List[Dict[str, str]], float, str]:
        """Parse recommendations section from response."""
        recommendations = []
        confidence = 0.8
        action_plan = ""

        current_rec = None
        in_recommendations = False
        
        for line in response_text.split('\n'):
            line = line.strip()
            
            if line.startswith("RECOMMENDATIONS:"):
                in_recommendations = True
                continue
            elif line.startswith("CONFIDENCE:") and in_recommendations:
                try:
                    conf_str = line.replace("CONFIDENCE:", "").strip()
                    confidence = float(conf_str)
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    pass
                continue
            elif line.startswith("ACTION_PLAN:"):
                action_plan = line.replace("ACTION_PLAN:", "").strip()
                continue
            
            if not in_recommendations:
                continue
                
            if line.startswith("RECOMMENDATION"):
                if current_rec:
                    recommendations.append(current_rec)
                current_rec = {}
            elif line.startswith("Priority:") and current_rec is not None:
                priority = line.replace("Priority:", "").strip().lower()
                current_rec["priority"] = priority if priority in ["high", "medium", "low"] else "medium"
            elif line.startswith("Action:") and current_rec is not None:
                current_rec["action"] = line.replace("Action:", "").strip()
            elif line.startswith("Reason:") and current_rec is not None:
                current_rec["reason"] = line.replace("Reason:", "").strip()
            elif line.startswith("Expected Impact:") and current_rec is not None:
                current_rec["expected_impact"] = line.replace("Expected Impact:", "").strip()

        # Add last recommendation
        if current_rec and "action" in current_rec:
            recommendations.append(current_rec)

        # Ensure all recommendations have required fields
        recommendations = [
            rec for rec in recommendations
            if "action" in rec and "reason" in rec and "priority" in rec
        ]

        return recommendations, confidence, action_plan or "Follow the recommendations in priority order"

    def _extract_issues_from_response(self, response: str) -> List[str]:
        """Extract issues from agent response text."""
        issues = []

        # Look for common issue indicators
        lines = response.split('\n')
        for line in lines:
            lower_line = line.lower()
            if any(keyword in lower_line for keyword in ["issue", "problem", "concern", "warning", "underperforming"]):
                issues.append(line.strip())

        return issues[:10]  # Limit to 10 issues


# Global instance
diagnosis_recommendation_agent = DiagnosisRecommendationAgent()

