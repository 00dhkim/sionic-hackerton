# 파일 업로드문서 파싱 요청

- https://storm-apis.sionic.im/parse-router/api/v2/parse/by-file
- POST

## request

curl --location --request POST 'https://storm-apis.sionic.im/parse-router/api/v2/parse/by-file' \
--header 'Authorization: Bearer <token>' \
--form 'file=@""' \
--form 'language="ko"' \
--form 'deleteOriginFile="true"'

## response

{
    "jobId": "defa_be5e9d960e8a45e39cf33069f1fae8d2",
    "state": "REQUESTED",
    "requestedAt": "2024-01-01T00:00:00Z"
}

# 문서 파싱 결과 조회

- https://storm-apis.sionic.im/parse-router/api/v2/parse/job/{jobId}
- GET

## request

curl --location --request GET 'https://storm-apis.sionic.im/parse-router/api/v2/parse/job/b03a4b58-8ae8-42b6-8b10-2ded87869861' \
--header 'Authorization: Bearer <token>'

## response

### 200

{
    "jobId": "defa_be5e9d960e8a45e39cf33069f1fae8d2",
    "state": "COMPLETED",
    "requestedAt": "2024-01-01T00:00:00Z",
    "completedAt": "2024-01-01T00:05:00Z",
    "pages": [
        {
            "pageNumber": 1,
            "content": "string"
        }
    ]
}

### 403 / 400

{
    "code": "APIKEY_NOT_FOUND",
    "message": "존재하지 않는 API 키입니다"
}