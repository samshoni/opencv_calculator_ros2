import cv2

class Button:
    def __init__(self, x, y, w, h, text):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text

    def draw(self, img, color=(50, 50, 50), text_color=(255, 255, 255)):
        # Button rectangle
        cv2.rectangle(img, (self.x, self.y), (self.x + self.w, self.y + self.h),
                      color, -1)

        # Centered text
        font_scale = 1
        thickness = 2
        (tw, th), _ = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX,
                                      font_scale, thickness)

        tx = self.x + (self.w - tw) // 2
        ty = self.y + (self.h + th) // 2

        cv2.putText(img, self.text, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                    text_color, thickness)

