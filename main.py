import sys
from PyQt5.QtWidgets import QApplication
from ui import PostureApp
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PostureApp()
    ex.show()
    sys.exit(app.exec_())