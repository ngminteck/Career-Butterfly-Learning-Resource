Here is a simple flow chart:

```mermaid
graph TD;
    Linkedin_Profile-->Automatic_Resume_Creator;
    Automatic_Resume_Creator-->Recommendation_Job;
    Resume-->Recommendation_Job;
    Recommendation_Job-->Job_filtering;
    Job_filtering-->Recommendation_Job;
    Recommendation_Job-->Company_Review;
    Company_Review-->Company_Interview_Review;
    Recommendation_Job-->Improving_Resume;
    Recommendation_Job-->Tech_Interview_Prepare_Suggestion;
    Company_Interview_Review-->Tech_Interview_Prepare_Suggestion;
    Tech_Interview_Prepare_Suggestion-->Leetcode;
    Tech_Interview_Prepare_Suggestion-->Learning-Resource;
    Tech_Interview_Prepare_Suggestion-->Mock_live_coding_Interview;
    Improving_Resume-->Automatic_Coverletter_writer;
    Automatic_Coverletter_writer->Auto_Applying;
    Improving_Resume-->Auto_Applying;
```
