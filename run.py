import shutil
import pytest
import os
import webbrowser
from conf.setting import REPORT_TYPE, PARALLEL_WORKERS


def _build_parallel_args() -> list:
    """根据 setting.py 中的 PARALLEL_WORKERS 构建 pytest-xdist 参数"""
    if not PARALLEL_WORKERS:
        return []
    workers = str(PARALLEL_WORKERS)  # 可以是 'auto' 或数字字符串
    # --dist=loadfile：同文件内用例顺序执行，防止接口关联数据竞争
    return [f"-n{workers}", "--dist=loadfile"]


if __name__ == "__main__":
    parallel_args = _build_parallel_args()

    if REPORT_TYPE == "allure":
        base_args = [
            "-s",
            "-v",
            "--alluredir=./report/temp",
            "./testcase",
            "--clean-alluredir",
            "--junitxml=./report/results.xml",
        ]
        pytest.main(base_args + parallel_args)

        shutil.copy("./environment.xml", "./report/temp")
        os.system("allure generate ./report/temp -o ./report/allureReport --clean")
        os.system("allure open ./report/allureReport")

    elif REPORT_TYPE == "tm":
        base_args = [
            "-vs",
            "--pytest-tmreport-name=testReport.html",
            "--pytest-tmreport-path=./report/tmreport",
        ]
        pytest.main(base_args + parallel_args)
        webbrowser.open_new_tab(os.getcwd() + "/report/tmreport/testReport.html")
