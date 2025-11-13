import rclpy
from rclpy.node import Node
import cv2
import mediapipe as mp
import math
import re
from .ui_buttons import Button


class CalculatorNode(Node):
    def __init__(self):
        super().__init__('calculator_node')
        self.get_logger().info("Calculator Node Started")

        # -------------------------
        # WEBCAM
        # -------------------------
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.get_logger().error("Error: Could not open webcam.")

        # -------------------------
        # CALCULATOR BUTTONS
        # -------------------------
        self.buttons = []
        btn_w = 60
        btn_h = 60
        start_x = 320  # Right-side placement (for 640 width)
        start_y = 80
        gap = 8

        keys = [
            ["7", "8", "9", "+"],
            ["4", "5", "6", "-"],
            ["1", "2", "3", "*"],
            ["0", "=", "/", "C"]
        ]

        for row_index, row in enumerate(keys):
            for col_index, key in enumerate(row):
                x = start_x + col_index * (btn_w + gap)
                y = start_y + row_index * (btn_h + gap)
                self.buttons.append(Button(x, y, btn_w, btn_h, key))

        # -------------------------
        # MEDIAPIPE HAND TRACKING
        # -------------------------
        mp_hands = mp.solutions.hands
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils

        # -------------------------
        # CALCULATOR STATE
        # -------------------------
        self.current_expression = ""
        self.result = ""
        self.last_mode = "IDLE"
        self.last_button_index = None

    # -----------------------------
    # BUTTON PRESS HANDLER
    # -----------------------------
    def on_button_press(self, label: str):
        if label == 'C':
            self.current_expression = ""
            self.result = ""
            return

        if label == '=':
            expr = self.current_expression.strip()
            if not expr:
                return

            # Allow only digits, operators and spaces
            if not re.fullmatch(r"[0-9+\-*/. ()]+", expr):
                self.result = "ERR"
                return

            try:
                value = eval(expr)
                self.result = str(value)
            except Exception:
                self.result = "ERR"
            return

        # For digits and operators
        if label in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                     '+', '-', '*', '/']:
            # If last action was "=", and result exists, start new expression
            if self.result and self.current_expression.endswith('='):
                self.current_expression = ""
                self.result = ""
            self.current_expression += label

    def run(self):
        while rclpy.ok():
            ret, frame = self.cap.read()
            if not ret:
                self.get_logger().error("Failed to grab frame")
                break

            # Flip for more natural interaction (mirror)
            frame = cv2.flip(frame, 1)

            # -------------------------
            # MEDIAPIPE PROCESSING
            # -------------------------
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)

            index_finger_tip = None
            mode = "IDLE"  # TAP / SAFE / IDLE
            current_button_index = None

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                lm = hand_landmarks.landmark
                h, w, _ = frame.shape

                # Tip points
                index_tip = (int(lm[8].x * w), int(lm[8].y * h))
                middle_tip = (int(lm[12].x * w), int(lm[12].y * h))

                index_finger_tip = index_tip

                # Check which fingers are up (non-thumb)
                index_up  = lm[8].y < lm[6].y
                middle_up = lm[12].y < lm[10].y
                ring_up   = lm[16].y < lm[14].y
                pinky_up  = lm[20].y < lm[18].y

                # ---------- MODE LOGIC ----------
                # TAP MODE: Only index up
                if index_up and not middle_up and not ring_up and not pinky_up:
                    mode = "TAP"

                # SAFE MODE: Index + middle up, close together
                elif index_up and middle_up:
                    dist = math.dist(index_tip, middle_tip)
                    threshold = h / 20  # scale with image height
                    if dist < threshold:
                        mode = "SAFE"
                    else:
                        mode = "IDLE"
                else:
                    mode = "IDLE"

                # Draw index fingertip
                cv2.circle(frame, index_finger_tip, 10, (0, 255, 0), -1)

                # If we are in TAP or SAFE, check which button (if any) is under fingertip
                if index_finger_tip is not None:
                    ix, iy = index_finger_tip
                    for i, button in enumerate(self.buttons):
                        if (button.x <= ix <= button.x + button.w and
                                button.y <= iy <= button.y + button.h):
                            current_button_index = i
                            break

            # -------------------------
            # DISPLAY MODE TEXT
            # -------------------------
            if mode == "TAP":
                mode_text = "Mode: TAP (1 finger)"
                mode_color = (0, 255, 0)  # Green
            elif mode == "SAFE":
                mode_text = "Mode: SAFE (2 fingers together)"
                mode_color = (0, 255, 255)  # Yellow
            else:
                mode_text = "Mode: IDLE"
                mode_color = (255, 255, 255)  # White

            cv2.putText(frame, mode_text, (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, mode_color, 2)

            # -------------------------
            # HANDLE BUTTON TAP
            # -------------------------
            # Only trigger when:
            # - We are in TAP mode
            # - Fingertip is on a button
            # - Either mode changed from non-TAP to TAP
            #   OR finger moved to a different button
            if mode == "TAP" and current_button_index is not None:
                if self.last_mode != "TAP" or self.last_button_index != current_button_index:
                    label = self.buttons[current_button_index].text
                    self.on_button_press(label)

            # Update last state for debounce
            self.last_mode = mode
            self.last_button_index = current_button_index

            # -------------------------
            # DRAW DISPLAY AREA
            # -------------------------
            # Background box for expression and result
            cv2.rectangle(frame, (20, 60), (300, 130), (40, 40, 40), -1)

            expr_display = self.current_expression
            if len(expr_display) > 18:
                expr_display = expr_display[-18:]  # show last chars only

            cv2.putText(frame, f"Expr: {expr_display}",
                        (30, 85), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)

            if self.result:
                cv2.putText(frame, f"Res: {self.result}",
                            (30, 115), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 0), 2)

            # -------------------------
            # DRAW CALCULATOR UI
            # -------------------------
            for button in self.buttons:
                button.draw(frame)

            cv2.imshow("OpenCV Calculator", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.cap.release()
        cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args)
    node = CalculatorNode()
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

