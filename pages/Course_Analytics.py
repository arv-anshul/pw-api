import json

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from requests import HTTPError, get

from src import AnalyticsSubmissions, AnalyticsUsers, courses_dict, get_live_course_df
from src.core.logger import get_logger
from src.models.analytics import QuizAnalytics

logger = get_logger(__name__)

# Page config
st.set_page_config("Course Analytics", "🎁", "wide")


@st.cache_resource
def get_analytics_data(
    course_name: str,
    cid: str,
) -> tuple[AnalyticsSubmissions, AnalyticsUsers, QuizAnalytics, pd.DataFrame]:
    url = f"https://learn.pwskills.com/course-analytics/{course_name}/{cid}"
    r = get(url)
    logger.info(f"[{r.status_code}]:{r.url}")

    if r.status_code != 200:
        logger.error("URL response is not 200.")
        raise HTTPError(f"{r.status_code} response: {url}")

    # Parse html with BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    data = json.loads(script.text)  # type: ignore

    # Get submission, user and quizAnalytics data
    submissions = data["props"]["pageProps"]["analytics"]["submissions"]
    users = data["props"]["pageProps"]["analytics"]["users"]
    quiz_analytics = data["props"]["pageProps"]["quizAnalytics"]

    return (
        AnalyticsSubmissions(**{"submissions": submissions}),
        AnalyticsUsers(**{"users": users}),
        QuizAnalytics(**{"quizAnalytics": quiz_analytics}),
        get_live_course_df(
            data["props"]["pageProps"]["sections"], courses_dict[cid], cid
        ),
    )


# --- --- --- --- --- --- --- --- --- --- --- --- --- --- #
# Sidebar
# --- --- --- --- --- --- --- --- --- --- --- --- --- --- #
with st.sidebar:
    cid = str(
        st.selectbox(
            "Select Course", courses_dict.keys(), format_func=lambda x: courses_dict[x]
        )
    )
    radio = st.radio("Select Analytics", ["Assignments Analytics", "Quiz Analytics"])

try:
    (sub, users, qz, lc) = get_analytics_data(courses_dict[cid], cid)
except KeyError:
    st.title("This course has not any analytics.")
    st.stop()

st.title(courses_dict[cid])

resource_type_count = lc["type"].value_counts().to_dict()
total_assignment_points = int(lc["totalPointsInAssignment"].sum())
total_video_duration = int(lc["duration"].sum() / 3600)

try:
    total_quiz_points = int(lc["totalQuestionsInQuiz"].sum())
except KeyError as e:
    lc[e] = pd.NA
    total_quiz_points = 0

col1, col2 = st.columns(2)
col1.markdown(
    f"""
    **:red[Max Points in Assignments:]** {total_assignment_points}  
    **:red[Max Points in Quiz:]** {total_quiz_points}  
    **:red[Total Duration of Lectures:]** {total_video_duration} Hours

    ---
    """
)

try:
    assign_count = resource_type_count["assignment"]
    quiz_count = resource_type_count["quiz"]
    video_count = resource_type_count["video"]
except KeyError as e:
    resource_type_count[e] = 0
else:
    col2.markdown(
        f"""
        **:red[Total No. of Assignment:]** {assign_count}  
        **:red[Total No. of Quizzes:]** {quiz_count}  
        **:red[Total No. of Lectures:]** {video_count}

        ---
        """
    )

if radio == "Assignments Analytics":
    # --- --- Top 3 Students --- --- #
    cols = st.columns(3)
    for i in range(3):
        student_submission = sub.submissions[i]
        student = users.users[i]

        # Display Profile Pic
        cols[i].write(student.get_img_link(), unsafe_allow_html=True)

        # Display Student Metrics
        cols[i].metric(
            f"**:green[{student.firstName} {student.lastName}]**",
            f"{student_submission.totalAssignmentsScore} • {student_submission.assignmentsMarkedCount}",
            help="Assignments Score • Assignments Marked Count",
        )
        cols[i].write("---")

    # --- --- Under 50 - Students --- --- #
    _, col_for_table, _ = st.columns([0.25, 0.5, 0.25])

    df1, df2 = users.get_df(), sub.get_df()
    df1["Name"] = df1["firstName"] + " " + df1["lastName"]
    df = pd.concat([df1, df2], axis=1)

    col_for_table.table(
        (
            df[["Name", "assignmentsMarkedCount", "totalAssignmentsScore"]]
            .rename(
                columns={
                    "assignmentsMarkedCount": "Marked",
                    "totalAssignmentsScore": "Total Score",
                }
            )
            .loc[3:]
        )
    )

elif radio == "Quiz Analytics":
    col, _ = st.columns([0.4, 0.6])
    col.header("Top 10 Students")

    df = qz.get_df()
    df["Name"] = df["firstName"] + " " + df["lastName"]
    col.table(df[["Name", "totalPoints"]])
