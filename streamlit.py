import streamlit as st
import boto3
from botocore.config import Config
from datetime import timedelta
import json
import altair as alt
import pandas as pd

AWS_S3_BUCKET = "fairlabs-shared"

# Create the clients
s3_client = boto3.client(
    's3', 
    aws_access_key_id=st.secrets["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws_secret_access_key"],
    region_name='ap-northeast-2'
)
lambda_client = boto3.client('lambda', 
    config=Config(
        read_timeout=900,
        connect_timeout=900,
        retries={"max_attempts": 0}
    ),
    aws_access_key_id=st.secrets["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws_secret_access_key"],
    region_name='ap-northeast-2'
)

# Clear the page
st.empty()

# Define the search box for the user to enter a query
keyword_query = st.text_input('Keyword Query', help="Enter keywords to search for similar articles.")
semantic_query = st.text_input('Semantic Query', help="Enter queries to search for similar articles.")

## Sidebar

# Title
st.sidebar.markdown("## Science & Technology Monitoring System (STMS)")

# Search parameters
st.sidebar.markdown("### Search settings")
start_date = st.sidebar.date_input("From:")
end_date = st.sidebar.date_input("To:")
search_similarity = st.sidebar.slider('Search Similariy', 0.1, 1.0, 0.5)  # min, max, default

# Clustering parameters
st.sidebar.markdown("### Clustering settings")
cluster_min_size = st.sidebar.number_input("Minimum cluster size", min_value=1, max_value=20, value=5, step=1)
cluster_top_n = st.sidebar.number_input("Top N clusters", min_value=1, max_value=20, value=5, step=1)
cluster_similarity = st.sidebar.slider('Clustering Similariy', 0.1, 1.0, 0.6)  # min, max, default

# ChatGPT parameters
st.sidebar.markdown("### ChatGPT settings")
_use_body = st.sidebar.checkbox('Topic Description')
_generate_summary = st.sidebar.checkbox('Issue report')
give_gpt_n_sample = st.sidebar.number_input("Title", min_value=1, max_value=20, value=5, step=1)
st.sidebar.number_input("Body", min_value=1, max_value=20, value=5, step=1)

_use_main_articles = False  # True
result = None

## Send request to the REST API when the user clicks the button
if st.button("Search"):
    print("Fetching results")
    # If the user enters a query, send a request to the REST API and display the returned text
    if keyword_query and semantic_query and start_date and end_date:
        end_date += timedelta(days=1)
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        # Spin the loading spinner while the request is being processed
        with st.spinner("Loading... It may take a few minutes"):
            # Invoke the lambda function
            response = lambda_client.invoke(
                FunctionName='semantic_search',
                InvocationType='RequestResponse', # Synchronous call
                Payload=json.dumps({
                    "keyword_query": keyword_query, 
                    "semantic_query": semantic_query, 
                    "start_date": start_date_str, 
                    "end_date": end_date_str,
                    "search_similarity": search_similarity,
                    "cluster_min_size": cluster_min_size,
                    "cluster_top_n": cluster_top_n,
                    "cluster_similarity": cluster_similarity,
                    "_use_body": _use_body,
                    "_use_main_articles": _use_main_articles,
                    "give_gpt_n_sample": give_gpt_n_sample
                })
            )
            result = json.loads(response['Payload'].read().decode())
            print("Result: ", result)

            if result and result['statusCode'] == 200:
                body = json.loads(result['body'])

                summaries = body['summaries']
                print("summaries: ", summaries)
                articles = body['articles']
                print("articles: ", articles)
                filepath = body['filepath']
                print("filepath: ", filepath)

                # Get the file from S3
                response = s3_client.get_object(Bucket=AWS_S3_BUCKET, Key=filepath.split("/")[-1])
                status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status == 200:
                    df = pd.read_csv(response.get("Body"))
                    print(f"Successful S3 get_object response. Status - {status}")
                else:
                    print(f"Unsuccessful S3 get_object response. Status - {status}")

                # ## Display the results in a chart
                # # Grid chart
                # selection = alt.selection_multi(fields=['titles'], bind='legend')
                # grid_chart = alt.Chart(df).mark_circle(size=60, stroke='#666', strokeWidth=1, opacity=0.3).encode(
                #     x=#'x',
                #     alt.X('x',
                #         scale=alt.Scale(zero=False),
                #         axis=alt.Axis(labels=False, ticks=False, domain=False)
                #     ),
                #     y=
                #     alt.Y('y',
                #         scale=alt.Scale(zero=False),
                #         axis=alt.Axis(labels=False, ticks=False, domain=False)
                #     ),
                #     # href='link:N',
                #     color=alt.Color('cluster:N', 
                #                     legend=alt.Legend(columns=1, symbolLimit=0, labelFontSize=14)
                #                 ),
                #     opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
                #     tooltip=['title', 'cluster', 'similarity']
                # ).properties(
                #     width=800,
                #     height=500
                # ).add_selection(
                #     selection
                # ).configure_legend(labelLimit= 0).configure_view(
                #     strokeWidth=0
                # ).configure(background="#FFFFFF").properties(
                #     title='R&D Monitoring'
                # )
                # grid_chart = grid_chart.interactive()
                # st.altair_chart(grid_chart, use_container_width=True)

                # # Count chart
                # class_counts = df.cluster.value_counts()
                # count_chart = alt.Chart(class_counts.reset_index()).mark_bar().encode(
                #     y=alt.Y('index:O', sort=alt.EncodingSortField(field='cluster', order='descending')),
                #     x='cluster:Q'
                # )
                # count_chart = count_chart.properties(title='Row counts by cluster', height=alt.Step(20))
                # count_chart = count_chart.configure_axis(labelFontSize=14, titleFontSize=16)
                # count_chart = count_chart.interactive()

                # Clustering Visualization
                if df.shape[0] > 5000:
                    df_clusters_sampled = df.sample(n=5000, random_state=1)
                else:
                    df_clusters_sampled = df.copy()

                selection = alt.selection_multi(fields=['title'], bind='legend')
                chart = alt.Chart(df_clusters_sampled).mark_circle(size=60, stroke='#666', strokeWidth=1, opacity=0.3).encode(
                    x=#'x',
                    alt.X('x',
                        scale=alt.Scale(zero=False),
                        axis=alt.Axis(labels=False, ticks=False, domain=False)
                    ),
                    y=
                    alt.Y('y',
                        scale=alt.Scale(zero=False),
                        axis=alt.Axis(labels=False, ticks=False, domain=False)
                    ),
                    # href='link:N',
                    color=alt.Color('kmeans_cluster:N', 
                                    legend=alt.Legend(columns=1, symbolLimit=0, labelFontSize=14)
                                ),
                    opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
                    tooltip=['title', 'kmeans_cluster', 'similarity']
                ).properties(
                    width=800,
                    height=500
                ).add_selection(
                    selection
                ).configure_legend(labelLimit= 0).configure_view(
                    strokeWidth=0
                ).configure(background="#FFFFFF").properties(
                    title='R&D Monitoring'
                )
                chart = chart.interactive()
                st.altair_chart(chart, use_container_width=True)
                
                # Display summaries
                for key, value in summaries.items():
                    st.markdown(f"### Cluster {int(key)} Topic: {value}")
                    for article in articles[key]:
                        st.write(f" - {article}")
                
                st.markdown("### Data")
                # Display dataframe with sorting column
                showed_data = df.copy()
                showed_data = showed_data[['cluster', 'topic', 'title', 'summary', 'author', 'published_date']]
                showed_data = showed_data.rename(columns={'summary': 'body'})
                st.dataframe(showed_data, use_container_width=True)

                # Download button
                @st.cache_data
                def convert_df(df):
                    return df.to_csv().encode('utf-8')
                csv = convert_df(showed_data)
                st.download_button(
                    label="Download",
                    data=csv,
                    file_name='FairLabsData.csv',
                    mime='text/csv',
                )

                # Generate summary
                if _generate_summary:
                    with st.spinner("Generating report ..."):
                            # Invoke the lambda function
                            response = lambda_client.invoke(
                                FunctionName='gpt_analytics',
                                InvocationType='RequestResponse', # Synchronous call
                                Payload=json.dumps({
                                    "filepath": filepath,
                                    "cluster_top_n": cluster_top_n,
                                    "give_gpt_n_sample": give_gpt_n_sample
                                })
                            )
                            result = json.loads(response['Payload'].read().decode())
                            print("Reports: ", result)
                            reports = json.loads(result['body'])
                            # Display the reports
                            st.markdown("### Reports")
                            for i, report in enumerate(reports):
                                st.markdown(f"##### Cluster: {i}")
                                st.markdown(f"##### Topic: {summaries[str(i)]}")
                                st.markdown(f"##### Summary: {report}")
                                # st.write(report)
            else:
                st.write("Error: Could not retrieve results")