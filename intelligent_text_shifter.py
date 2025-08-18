from typing import Dict, List
import math

class IntelligentTextShifter:
    def __init__(self, context: Dict, original_text: str, new_text: str):
        self.context = context
        self.original_text = original_text.strip()
        self.new_text = new_text.strip()
        self.original_bbox = context['original_bbox']
        
    def calculate_new_position(self) -> Dict:
        """
        Calculate new position based on context and text length change
        """
        strategy = self._determine_shifting_strategy()
        result = self._apply_shifting_strategy(strategy)
        
        # Add shift calculations
        result['shift_x'] = result['bbox'][0] - self.original_bbox[0]
        result['shift_y'] = result['bbox'][1] - self.original_bbox[1]
        
        return result
    
    def _determine_shifting_strategy(self) -> str:
        """
        Determine the best shifting strategy based on context
        More conservative approach to prevent unwanted shifting
        """
        # Only apply special shifting for very clear cases
        if self.context['is_list_item']:
            return 'list_item'
        elif self.context['is_header'] and self.context['alignment'] == 'center' and self.context['center_ratio'] <= 0.02:
            return 'centered_header'
        elif self.context['alignment'] == 'center' and self.context['center_ratio'] <= 0.02:
            return 'centered_text'
        elif self.context['alignment'] == 'right' and self.context['right_ratio'] <= 0.05:
            return 'right_aligned'
        elif self.context['is_justified']:
            return 'justified'
        else:
            # Default to left alignment for most text to prevent unwanted shifting
            return 'left_aligned'
    
    def _apply_shifting_strategy(self, strategy: str) -> Dict:
        """
        Apply the appropriate shifting strategy
        """
        strategies = {
            'list_item': self._shift_list_item,
            'centered_header': self._shift_centered_header,
            'centered_text': self._shift_centered_text,
            'right_aligned': self._shift_right_aligned,
            'justified': self._shift_justified,
            'left_aligned': self._shift_left_aligned
        }
        
        return strategies.get(strategy, self._shift_left_aligned)()
    
    def _shift_list_item(self) -> Dict:
        """
        Keep bullet position fixed, shift content right
        """
        # Calculate new width based on text change
        new_width = self._estimate_text_width(self.new_text, self.context['font_size'])
        
        # Keep original left position (bullet alignment preserved)
        new_left = self.original_bbox[0]
        new_right = new_left + new_width
        
        # Check for overflow
        available_right = self.context['available_space']['right']
        if new_right > (self.original_bbox[2] + available_right):
            # Text will overflow, consider line wrapping
            return self._handle_overflow('list_item', new_width)
        
        return {
            'bbox': [
                new_left,
                self.original_bbox[1],
                new_right,
                self.original_bbox[3]
            ],
            'strategy': 'list_item',
            'overflow_risk': False
        }
    
    def _shift_centered_header(self) -> Dict:
        """
        Recalculate center position for headers
        """
        new_width = self._estimate_text_width(self.new_text, self.context['font_size'])
        page_width = self.context['page_width']
        
        # Center the new text on the page
        new_left = (page_width - new_width) / 2
        new_right = new_left + new_width
        
        # Ensure it doesn't go off page
        if new_left < 0:
            new_left = 20  # Small margin
            new_right = new_left + new_width
        
        return {
            'bbox': [
                new_left,
                self.original_bbox[1],
                new_right,
                self.original_bbox[3]
            ],
            'strategy': 'centered_header',
            'overflow_risk': new_right > page_width
        }
    
    def _shift_centered_text(self) -> Dict:
        """
        Recalculate center position for regular centered text
        """
        new_width = self._estimate_text_width(self.new_text, self.context['font_size'])
        
        # Calculate original center point
        original_center = (self.original_bbox[0] + self.original_bbox[2]) / 2
        
        # Maintain center alignment around the same point
        new_left = original_center - (new_width / 2)
        new_right = new_left + new_width
        
        # Check boundaries
        if new_left < 0:
            new_left = 10
            new_right = new_left + new_width
        elif new_right > self.context['page_width']:
            new_right = self.context['page_width'] - 10
            new_left = new_right - new_width
        
        return {
            'bbox': [
                new_left,
                self.original_bbox[1],
                new_right,
                self.original_bbox[3]
            ],
            'strategy': 'centered_text',
            'overflow_risk': False
        }
    
    def _shift_right_aligned(self) -> Dict:
        """
        Keep right edge fixed, expand left
        """
        new_width = self._estimate_text_width(self.new_text, self.context['font_size'])
        original_right = self.original_bbox[2]
        
        # Keep right edge fixed
        new_left = original_right - new_width
        new_right = original_right
        
        # Check if it goes too far left
        if new_left < 0:
            new_left = 10
            new_right = new_left + new_width
        
        return {
            'bbox': [
                new_left,
                self.original_bbox[1],
                new_right,
                self.original_bbox[3]
            ],
            'strategy': 'right_aligned',
            'overflow_risk': new_left < 0
        }
    
    def _shift_justified(self) -> Dict:
        """
        Handle justified text - may need line breaking
        """
        new_width = self._estimate_text_width(self.new_text, self.context['font_size'])
        original_width = self.original_bbox[2] - self.original_bbox[0]
        
        # Check if text significantly exceeds original width
        width_increase = (new_width - original_width) / original_width
        needs_reflow = width_increase > 0.3  # 30% increase triggers reflow
        
        if needs_reflow:
            # Keep line width, text will need to reflow
            return {
                'bbox': self.original_bbox,
                'strategy': 'justified',
                'overflow_risk': True,
                'needs_line_break': True,
                'suggested_line_width': self.original_bbox[2] - self.original_bbox[0]
            }
        else:
            # Text fits within reasonable bounds
            return {
                'bbox': [
                    self.original_bbox[0],
                    self.original_bbox[1],
                    self.original_bbox[0] + new_width,
                    self.original_bbox[3]
                ],
                'strategy': 'justified',
                'overflow_risk': False
            }
    
    def _shift_left_aligned(self) -> Dict:
        """
        Keep left edge fixed, let right edge expand
        """
        new_width = self._estimate_text_width(self.new_text, self.context['font_size'])
        
        # Keep left position, expand right
        new_left = self.original_bbox[0]
        new_right = new_left + new_width
        
        # Check for overflow to the right
        page_width = self.context['page_width']
        overflow_risk = new_right > (page_width - 20)  # 20pt margin
        
        if overflow_risk:
            # Consider word wrapping or font size adjustment
            return self._handle_overflow('left_aligned', new_width)
        
        return {
            'bbox': [
                new_left,
                self.original_bbox[1],
                new_right,
                self.original_bbox[3]
            ],
            'strategy': 'left_aligned',
            'overflow_risk': False
        }
    
    def _handle_overflow(self, strategy: str, required_width: float) -> Dict:
        """
        Handle text overflow scenarios
        """
        available_width = self.context['page_width'] - self.original_bbox[0] - 20  # margin
        
        if required_width > available_width:
            # Text definitely won't fit in one line
            return {
                'bbox': self.original_bbox,
                'strategy': f'{strategy}_overflow',
                'overflow_risk': True,
                'needs_line_break': True,
                'available_width': available_width,
                'required_width': required_width
            }
        else:
            # Might fit with adjustment
            return {
                'bbox': [
                    self.original_bbox[0],
                    self.original_bbox[1],
                    self.original_bbox[0] + available_width,
                    self.original_bbox[3]
                ],
                'strategy': f'{strategy}_constrained',
                'overflow_risk': True
            }
    
    def _estimate_text_width(self, text: str, font_size: float) -> float:
        """
        Estimate text width based on character count and font size
        
        This is a rough estimation. For more accuracy, we could:
        1. Use actual font metrics from PyMuPDF
        2. Account for specific font families
        3. Handle kerning and spacing
        """
        if not text.strip():
            return 0
        
        # Character width multipliers for common font types
        # These are approximate values based on typical font characteristics
        char_width_factor = 0.6  # Default for most fonts
        
        # Adjust for font characteristics (could be enhanced with actual font analysis)
        estimated_width = len(text) * font_size * char_width_factor
        
        # Add some padding for spacing
        return estimated_width * 1.1
    
    def get_alignment_summary(self) -> Dict:
        """
        Get a summary of the alignment analysis and strategy
        """
        return {
            'original_alignment': self.context['alignment'],
            'is_list_item': self.context['is_list_item'],
            'is_header': self.context['is_header'],
            'is_justified': self.context['is_justified'],
            'recommended_strategy': self._determine_shifting_strategy(),
            'text_length_change': len(self.new_text) - len(self.original_text),
            'width_estimate_ratio': self._estimate_text_width(self.new_text, self.context['font_size']) / 
                                  self._estimate_text_width(self.original_text, self.context['font_size']) if self.original_text else 1.0
        }
